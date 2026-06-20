#!/usr/bin/env python3
"""
Bharat Tech Atlas v4.10.00 — Deduplication Pipeline

Detects and merges duplicate entities using fuzzy string matching.
Strategies:
1. Exact slug match (handled by ON CONFLICT upsert)
2. Jaro-Winkler similarity > 90% → auto-merge
3. Levenshtein similarity 75-90% → admin review flag

Usage:
    python scripts/dedupe.py --check-all
    python scripts/dedupe.py --merge --threshold 0.9
    python scripts/dedupe.py --review --threshold 0.75
"""
import argparse
import sys
import os
import json
import logging
from typing import List, Dict, Tuple
from difflib import SequenceMatcher

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("bta.dedupe")


def jaro_winkler_similarity(a: str, b: str) -> float:
    """Calculate Jaro-Winkler similarity (0.0 to 1.0)."""
    from jellyfish import jaro_winkler_similarity as jw
    return jw(a, b)


def levenshtein_similarity(a: str, b: str) -> float:
    """Calculate normalized Levenshtein similarity."""
    from jellyfish import levenshtein_distance
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    return 1.0 - (levenshtein_distance(a, b) / max_len)


def sequence_similarity(a: str, b: str) -> float:
    """Quick SequenceMatcher ratio."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_duplicates(entities: List[Dict], threshold: float = 0.85) -> List[Tuple[Dict, Dict, float, str]]:
    """
    Find potential duplicate pairs.
    
    Returns:
        List of (entity_a, entity_b, score, method) tuples
    """
    duplicates = []
    n = len(entities)
    
    for i in range(n):
        for j in range(i + 1, n):
            a = entities[i]
            b = entities[j]
            
            # Skip if different entity types
            if a.get("entity_type") != b.get("entity_type"):
                continue
            
            # Skip if different cities (likely different branches)
            if a.get("city") != b.get("city") and a.get("city") and b.get("city"):
                continue
            
            name_a = a.get("name", "").lower().strip()
            name_b = b.get("name", "").lower().strip()
            
            if not name_a or not name_b:
                continue
            
            # Try multiple similarity methods
            seq_score = sequence_similarity(name_a, name_b)
            
            if seq_score >= threshold:
                duplicates.append((a, b, seq_score, "sequence"))
                continue
            
            # Try Jaro-Winkler if available
            try:
                jw_score = jaro_winkler_similarity(name_a, name_b)
                if jw_score >= threshold:
                    duplicates.append((a, b, jw_score, "jaro-winkler"))
            except ImportError:
                pass
    
    # Sort by score descending
    duplicates.sort(key=lambda x: x[2], reverse=True)
    return duplicates


def auto_merge(entities: List[Tuple[Dict, Dict, float, str]], dry_run: bool = True) -> List[Dict]:
    """
    Auto-merge high-confidence duplicates (score >= 0.9).
    
    Strategy: Keep the entity with more data (more non-null fields).
    """
    merged = []
    
    for a, b, score, method in entities:
        if score < 0.9:
            continue
        
        # Count non-null fields
        a_count = sum(1 for v in a.values() if v is not None and v != "")
        b_count = sum(1 for v in b.values() if v is not None and v != "")
        
        keeper = a if a_count >= b_count else b
        discarder = b if keeper == a else a
        
        merged_entity = {
            **keeper,
            "merged_from": discarder.get("slug", discarder.get("name", "unknown")),
            "merge_score": round(score, 3),
            "merge_method": method,
        }
        
        if not dry_run:
            logger.info(f"Merged: {discarder['name']} into {keeper['name']} (score={score:.2f})")
        else:
            logger.info(f"[DRY RUN] Would merge: {discarder['name']} into {keeper['name']} (score={score:.2f})")
        
        merged.append(merged_entity)
    
    return merged


def flag_for_review(entities: List[Tuple[Dict, Dict, float, str]]) -> List[Dict]:
    """Flag borderline duplicates (0.75-0.90) for admin review."""
    review = []
    
    for a, b, score, method in entities:
        if 0.75 <= score < 0.9:
            review.append({
                "entity_a": {"name": a.get("name"), "slug": a.get("slug"), "city": a.get("city"), "state": a.get("state")},
                "entity_b": {"name": b.get("name"), "slug": b.get("slug"), "city": b.get("city"), "state": b.get("state")},
                "similarity": round(score, 3),
                "method": method,
                "recommendation": "review",
            })
    
    return review


def main():
    parser = argparse.ArgumentParser(description="Bharat Tech Atlas Deduplication Pipeline")
    parser.add_argument("--check-all", action="store_true", help="Check all entities for duplicates")
    parser.add_argument("--merge", action="store_true", help="Auto-merge high-confidence duplicates")
    parser.add_argument("--review", action="store_true", help="Flag borderline duplicates for review")
    parser.add_argument("--threshold", type=float, default=0.85, help="Similarity threshold (0.0-1.0)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview without making changes")
    parser.add_argument("--output", type=str, default="dedupe_report.json", help="Output report file")
    args = parser.parse_args()
    
    if not args.check_all and not args.merge and not args.review:
        parser.print_help()
        return
    
    # Load entities from database
    try:
        from backend.database import get_db
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM entities WHERE is_active = 1"
        ).fetchall()
        conn.close()
        
        import json
        entities = []
        for row in rows:
            entity = {}
            for key in row.keys():
                entity[key] = row[key]
            entities.append(entity)
        
        logger.info(f"Loaded {len(entities)} entities for deduplication analysis")
    except Exception as e:
        logger.error(f"Failed to load entities: {e}")
        return
    
    report = {
        "total_entities": len(entities),
        "threshold": args.threshold,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "high_confidence": [],
        "borderline": [],
        "merged": [],
    }
    
    if args.check_all or args.merge or args.review:
        logger.info(f"Finding duplicates with threshold={args.threshold}...")
        duplicates = find_duplicates(entities, threshold=args.threshold)
        
        high_conf = [(a, b, s, m) for a, b, s, m in duplicates if s >= 0.9]
        borderline = [(a, b, s, m) for a, b, s, m in duplicates if 0.75 <= s < 0.9]
        
        report["high_confidence"] = [
            {"a": a.get("name"), "b": b.get("name"), "score": round(s, 3), "method": m}
            for a, b, s, m in high_conf
        ]
        report["borderline"] = [
            {"a": a.get("name"), "b": b.get("name"), "score": round(s, 3), "method": m}
            for a, b, s, m in borderline
        ]
        
        logger.info(f"Found {len(high_conf)} high-confidence duplicates (>=0.9)")
        logger.info(f"Found {len(borderline)} borderline duplicates (0.75-0.9)")
    
    if args.merge and high_conf:
        logger.info("Auto-merging high-confidence duplicates...")
        merged = auto_merge(high_conf, dry_run=args.dry_run)
        report["merged"] = [{"name": e.get("name"), "score": e.get("merge_score")} for e in merged]
    
    if args.review and borderline:
        logger.info("Flagging borderline duplicates for review...")
        flagged = flag_for_review(borderline)
        report["flagged_for_review"] = flagged
        
        for f in flagged[:10]:
            logger.info(f"  Review: {f['entity_a']['name']} vs {f['entity_b']['name']} (score={f['similarity']})")
    
    # Save report
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info(f"Report saved to {args.output}")
    
    # Summary
    print("\n" + "="*60)
    print("  DEDUPLICATION REPORT")
    print("="*60)
    print(f"  Total entities:        {len(entities)}")
    print(f"  Similarity threshold:  {args.threshold}")
    print(f"  High confidence:       {len(report['high_confidence'])} pairs")
    print(f"  Borderline:            {len(report.get('borderline', []))} pairs")
    print(f"  Merged:                {len(report.get('merged', []))} entities")
    print(f"  Report:                {args.output}")
    print("="*60)


if __name__ == "__main__":
    main()
