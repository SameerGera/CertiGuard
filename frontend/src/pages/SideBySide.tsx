import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import type { BidderResult, CriterionResult } from '../types/api'
import { getReviewQueue } from '../hooks/useApi'
import CriterionResultComponent from '../components/CriterionResult'
import OverrideModal from '../components/OverrideModal'

interface SideBySideProps {
  tenderId: string
}

export default function SideBySide({ tenderId }: SideBySideProps) {
  const { bidderId } = useParams<{ bidderId: string }>()
  const navigate = useNavigate()
  const [bidder, setBidder] = useState<BidderResult | null>(null)
  const [selectedCriterion, setSelectedCriterion] = useState<CriterionResult | null>(null)
  const [showOverride, setShowOverride] = useState(false)
  const [loading, setLoading] = useState(true)
  const [currentTenderId] = useState(tenderId || 'T001')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!bidderId) return
    setLoading(true)
    getReviewQueue(currentTenderId)
      .then(data => {
        const foundBidder = data.bidders.find(b => b.bidder_id === bidderId)
        if (foundBidder) {
          setBidder(foundBidder)
        }
      })
      .catch(err => console.error('Failed to fetch bidder:', err))
      .finally(() => setLoading(false))
  }, [bidderId, currentTenderId, refreshKey])

  if (!bidderId) {
    return <div className="text-center py-12 text-slate-500">Select a bidder from the queue</div>
  }

  if (loading) {
    return <div className="text-center py-12 text-slate-500">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/queue')} className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 font-medium">
          ← Back
        </button>
        <div>
          <h2 className="text-2xl font-bold text-slate-800">{bidder?.bidder_name}</h2>
          <p className="text-slate-500">{bidder?.bidder_id}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-4">
          <h3 className="font-semibold text-slate-800">AI Reasoning</h3>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 divide-y divide-slate-100">
            {bidder?.criterion_results.map((criterion) => (
              <div
                key={criterion.criterion_id}
                onClick={() => setSelectedCriterion(criterion)}
                className={`p-4 cursor-pointer hover:bg-slate-50 ${
                  selectedCriterion?.criterion_id === criterion.criterion_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                }`}
              >
                <CriterionResultComponent criterion={criterion} />
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="font-semibold text-slate-800">Source Document</h3>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 min-h-[600px]">
            {selectedCriterion ? (
              <DocumentViewer criterion={selectedCriterion} bidderId={bidderId} />
            ) : (
              <div className="h-[600px] flex items-center justify-center text-slate-500">
                Select a criterion to view source evidence
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedCriterion && (
        <div className="fixed bottom-6 right-6 flex gap-3">
          <button
            onClick={() => setShowOverride(true)}
            className="px-6 py-3 bg-amber-500 text-white rounded-lg hover:bg-amber-600 transition"
          >
            Override Verdict
          </button>
        </div>
      )}

      {showOverride && selectedCriterion && (
        <OverrideModal
          criterion={selectedCriterion}
          bidderId={bidderId}
          onClose={() => setShowOverride(false)}
          onSubmit={() => {
            setShowOverride(false)
            setRefreshKey(k => k + 1)
            navigate('/queue', { state: { refresh: true } })
          }}
        />
      )}
    </div>
  )
}

function getEvidenceFile(criterionId: string, bidderId: string): { filename: string; label: string } {
  const mapping: Record<string, { filename: string; label: string }> = {
    'C001': { filename: `${bidderId}_gst.pdf`, label: 'GST Certificate' },
    'C002': { filename: `${bidderId}_experience.pdf`, label: 'Experience Certificate' },
    'C003': { filename: `${bidderId}_turnover.pdf`, label: 'Turnover/ITR Document' },
  }
  return mapping[criterionId] || { filename: `${bidderId}_gst.pdf`, label: 'Document' }
}

function DocumentViewer({ criterion, bidderId }: { criterion: CriterionResult; bidderId: string }) {
  const [showBoxes, setShowBoxes] = useState(true)
  const [zoom, setZoom] = useState(1)
  const evidence = getEvidenceFile(criterion.criterion_id, bidderId)

  const getBoxes = () => {
    if (criterion.criterion_id === 'C001') {
      return [
        { ref: 'GSTIN', x: 100, y: 180, w: 300, h: 30 },
        { ref: 'Company Name', x: 100, y: 220, w: 350, h: 25 },
        { ref: 'Status', x: 100, y: 260, w: 150, h: 20 },
      ]
    }
    if (criterion.criterion_id === 'C002') {
      return [
        { ref: 'Years', x: 100, y: 180, w: 200, h: 30 },
        { ref: 'Company', x: 100, y: 220, w: 300, h: 25 },
      ]
    }
    if (criterion.criterion_id === 'C003') {
      return [
        { ref: 'Turnover', x: 100, y: 180, w: 250, h: 30 },
        { ref: 'Company', x: 100, y: 220, w: 300, h: 25 },
      ]
    }
    return [{ ref: 'Content', x: 100, y: 200, w: 400, h: 50 }]
  }

  return (
    <div className="relative w-full h-full flex flex-col">
      <div className="flex items-center gap-4 mb-4 p-2 bg-slate-50 rounded-lg">
        <span className="text-sm font-medium text-slate-700">{evidence.label}</span>
        <button
          onClick={() => setShowBoxes(!showBoxes)}
          className={`px-3 py-1 text-sm rounded-lg ${showBoxes ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'}`}
        >
          {showBoxes ? 'Hide Boxes' : 'Show Boxes'}
        </button>
        <div className="flex items-center gap-2">
          <button onClick={() => setZoom(Math.max(0.5, zoom - 0.25))} className="w-8 h-8 flex items-center justify-center border border-slate-300 rounded hover:bg-slate-50">−</button>
          <span className="text-sm text-slate-600">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom(Math.min(2, zoom + 0.25))} className="w-8 h-8 flex items-center justify-center border border-slate-300 rounded hover:bg-slate-50">+</button>
        </div>
        <span className="text-sm text-slate-500">Page 1</span>
      </div>

      <div className="flex-1 bg-slate-100 rounded-lg overflow-auto flex items-center justify-center p-4">
        <div className="relative bg-white shadow-lg" style={{ width: 595 * zoom, height: 842 * zoom }}>
          <div className="absolute inset-0 p-8">
            <div className="text-xs text-slate-400 mb-4">{evidence.filename}</div>
            <h3 className="text-lg font-bold mb-4">{evidence.label}</h3>
            <div className="space-y-3 text-sm">
              <p><span className="text-slate-500">Company Name:</span> <span className="font-medium">{bidderId === 'B001' ? 'Alpha Textiles Ltd' : bidderId === 'B002' ? 'Beta Garments Pvt Ltd' : 'Gamma Industries'}</span></p>
              <p><span className="text-slate-500">Status:</span> <span className="font-medium text-green-600">{criterion.verdict === 'NOT_ELIGIBLE' ? 'Issues Found' : 'Verified'}</span></p>
              <p><span className="text-slate-500">Verdict:</span> <span className={`font-medium ${criterion.verdict === 'ELIGIBLE' ? 'text-green-600' : criterion.verdict === 'NOT_ELIGIBLE' ? 'text-red-600' : 'text-amber-600'}`}>{criterion.verdict}</span></p>
              <p><span className="text-slate-500">AI Confidence:</span> <span className="font-medium">{Math.round(criterion.ai_confidence * 100)}%</span></p>
            </div>
            <div className="mt-8 p-4 bg-slate-50 rounded text-xs text-slate-500">
              {criterion.reason}
            </div>
          </div>
          {showBoxes && getBoxes().map((box, i) => (
            <div key={box.ref} className="absolute border-2 border-blue-500 bg-blue-500/20" style={{ 
              left: (box.x + 32) * zoom, 
              top: (box.y + 60) * zoom, 
              width: box.w * zoom, 
              height: box.h * zoom 
            }}>
              <span className="absolute -top-5 left-0 bg-blue-500 text-white text-xs px-1 rounded">{i + 1}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}