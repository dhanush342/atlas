import React, { useState } from 'react'

export default function StatsBar({ overview, viewportSummary, featureCount, loading, isMobile }) {
  const [collapsed, setCollapsed] = useState(false)
  const [showNationwide, setShowNationwide] = useState(true)

  if (!overview) return null

  const mapped = overview.mapped || overview
  const nationwide = overview.nationwide || null

  const cards = showNationwide && nationwide ? [
    {
      label: 'In View',
      value: viewportSummary?.count || featureCount,
      icon: '📍',
      desc: 'Entities visible on current map viewport',
    },
    {
      label: 'Mapped',
      value: mapped.total_entities,
      icon: '🏢',
      desc: 'Curated entities in our database',
      subtitle: 'local',
    },
    {
      label: 'Startups',
      value: nationwide.dpiit_startups,
      icon: '🚀',
      desc: 'DPIIT-registered startups nationwide (PIB 2026)',
      subtitle: 'nationwide',
      format: 'lakhs',
    },
    {
      label: 'Women-led',
      value: nationwide.women_led_startups,
      icon: '👩',
      desc: 'Women-led startups nationwide (PIB 2026)',
      subtitle: 'nationwide',
      format: 'lakhs',
    },
    {
      label: 'Unicorns',
      value: nationwide.unicorns,
      icon: '🦄',
      desc: 'Billion-dollar companies nationwide',
      subtitle: 'nationwide',
    },
    {
      label: 'Funding',
      value: mapped.total_funding_display,
      icon: '💰',
      desc: 'Mapped entities only — not total Indian startup funding',
      isText: true,
    },
  ] : [
    {
      label: 'In View',
      value: viewportSummary?.count || featureCount,
      icon: '📍',
      desc: 'Entities visible on current map viewport',
    },
    {
      label: 'Mapped',
      value: mapped.total_entities,
      icon: '🏢',
      desc: 'Curated entities in our database',
    },
    {
      label: 'Startups',
      value: mapped.by_type?.startup || 0,
      icon: '🚀',
      desc: 'Mapped startups in our dataset',
    },
    {
      label: 'Unicorns',
      value: mapped.unicorn_count || 0,
      icon: '🦄',
      desc: 'Valued >$1B in our dataset',
    },
    {
      label: 'Women-led',
      value: mapped.women_led_count || 0,
      icon: '👩',
      desc: 'Women-led in our dataset',
    },
    {
      label: 'Funding',
      value: mapped.total_funding_display,
      icon: '💰',
      desc: 'Mapped entities only',
      isText: true,
    },
  ]

  const formatValue = (value, format) => {
    if (typeof value !== 'number') return value
    if (format === 'lakhs') {
      if (value >= 100000) return `${(value / 100000).toFixed(2)}L+`
      return value.toLocaleString()
    }
    return value.toLocaleString()
  }

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
      {/* Toggle bar */}
      <div className="flex justify-center items-center gap-2 mb-2">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="pointer-events-auto glass rounded-full px-3 py-1 text-xs text-atlas-muted hover:text-atlas-text transition-colors shadow-lg"
        >
          {collapsed ? '▲ Show Stats' : '▼ Hide'}
        </button>
        {nationwide && (
          <button
            onClick={() => setShowNationwide(!showNationwide)}
            className={`pointer-events-auto glass rounded-full px-3 py-1 text-xs transition-colors shadow-lg ${showNationwide ? 'bg-green-500/20 text-green-300' : 'text-atlas-muted hover:text-atlas-text'}`}
            title={showNationwide ? 'Showing nationwide PIB stats' : 'Showing mapped stats only'}
          >
            {showNationwide ? '🌐 Nationwide' : '📍 Mapped Only'}
          </button>
        )}
      </div>

      {!collapsed && (
        <div className={`flex items-stretch gap-2 sm:gap-3 px-3 sm:px-4 pointer-events-auto animate-fade-in ${isMobile ? 'overflow-x-auto pb-1 scrollbar-thin' : ''}`}>
          {cards.map((card) => (
            <div
              key={card.label}
              className={`relative rounded-2xl border border-atlas-border shadow-lg px-3 sm:px-4 py-2.5 sm:py-3 min-w-[100px] sm:min-w-[120px] cursor-default transition-all hover:scale-[1.02] ${
                card.subtitle === 'nationwide' 
                  ? 'bg-gradient-to-br from-green-900/30 to-atlas-bg/90 border-green-500/30' 
                  : 'bg-atlas-bg/90'
              }`}
              title={card.desc}
            >
              {card.subtitle === 'nationwide' && (
                <span className="absolute -top-1.5 -right-1.5 w-3 h-3 rounded-full bg-green-500 animate-pulse" />
              )}
              <div className="flex items-start gap-2.5">
                <span className="text-lg mt-0.5">{card.icon}</span>
                <div>
                  <p className="text-base font-bold text-atlas-text leading-none tabular-nums">
                    {formatValue(card.value, card.format)}
                  </p>
                  <p className="text-[10px] text-atlas-muted leading-none mt-1.5 uppercase tracking-wider font-medium">
                    {card.label}
                  </p>
                  {card.subtitle && (
                    <p className={`text-[9px] leading-none mt-0.5 font-medium ${
                      card.subtitle === 'nationwide' ? 'text-green-400' : 'text-atlas-muted/50'
                    }`}>
                      {card.subtitle === 'nationwide' ? 'NATIONWIDE' : 'MAPPED'}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
