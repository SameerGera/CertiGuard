import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Document, Page, pdfjs } from 'react-pdf'
import type { BidderResult, CriterionResult } from '../types/api'
import { getReviewQueue } from '../hooks/useApi'
import CriterionResultComponent from '../components/CriterionResult'
import OverrideModal from '../components/OverrideModal'

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`

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

  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false)

  if (!bidderId) {
    return <div className="text-center py-12 text-slate-500">Select a bidder from the queue</div>
  }

  if (loading) {
    return <div className="text-center py-12 text-slate-500">Loading...</div>
  }

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-4 pb-4">
        <button onClick={() => navigate('/queue')} className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 font-medium">
          ← Back
        </button>
        <div>
          <h2 className="text-xl font-bold text-slate-800">{bidder?.bidder_name}</h2>
          <p className="text-sm text-slate-500">{bidder?.bidder_id}</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex gap-4 overflow-hidden">
        {/* Left Panel - AI Reasoning (Collapsible) */}
        <div className={`${leftPanelCollapsed ? 'w-12' : 'w-80'} transition-all duration-300 flex-shrink-0`}>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 h-full flex flex-col">
            {/* Toggle Button */}
            <button 
              onClick={() => setLeftPanelCollapsed(!leftPanelCollapsed)}
              className="p-2 hover:bg-slate-50 border-b border-slate-200 flex items-center justify-center"
            >
              <span className="text-lg">{leftPanelCollapsed ? '☰' : '←'}</span>
            </button>
            
            {!leftPanelCollapsed && (
              <>
                <div className="p-3 border-b border-slate-200">
                  <h3 className="font-semibold text-slate-800">AI Reasoning</h3>
                  <p className="text-xs text-slate-500">Click to view details</p>
                </div>
                <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
                  {bidder?.criterion_results.map((criterion) => (
                    <div
                      key={criterion.criterion_id}
                      onClick={() => setSelectedCriterion(criterion)}
                      className={`p-3 cursor-pointer hover:bg-slate-50 ${
                        selectedCriterion?.criterion_id === criterion.criterion_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                      }`}
                    >
                      <CriterionResultComponent criterion={criterion} />
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Center - PDF Viewer */}
        <div className="flex-1 min-w-0">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 h-full overflow-hidden">
            {selectedCriterion ? (
              <DocumentViewer criterion={selectedCriterion} bidderId={bidderId} />
            ) : (
              <div className="h-full flex items-center justify-center text-slate-500">
                Select a criterion from the left panel to view source evidence
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Override Button */}
      {selectedCriterion && (
        <div className="pt-4 flex justify-end">
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
  const [numPages, setNumPages] = useState<number>(0)
  const [pageNumber, setPageNumber] = useState(1)
  const evidence = getEvidenceFile(criterion.criterion_id, bidderId)
  
  // Construct the path to the PDF file
  const pdfPath = `/test_data/bidders/${evidence.filename}`

  // Get verification details from criterion
  const checks = criterion.verification_checks || []

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages)
  }

  return (
    <div className="w-full h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-4 mb-4 p-2 bg-slate-50 rounded-lg">
        <span className="text-sm font-medium text-slate-700">{evidence.label}</span>
        {numPages > 0 && (
          <div className="flex items-center gap-2">
            <button 
              onClick={() => setPageNumber(p => Math.max(1, p - 1))}
              disabled={pageNumber <= 1}
              className="px-2 py-1 text-sm border border-slate-300 rounded disabled:opacity-50"
            >
              ‹
            </button>
            <span className="text-sm text-slate-600">{pageNumber} / {numPages}</span>
            <button 
              onClick={() => setPageNumber(p => Math.min(numPages, p + 1))}
              disabled={pageNumber >= numPages}
              className="px-2 py-1 text-sm border border-slate-300 rounded disabled:opacity-50"
            >
              ›
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 bg-slate-100 rounded-lg overflow-auto flex items-start justify-center p-4">
        <div className="flex gap-4">
          {/* PDF Viewer */}
          <div className="bg-white shadow-lg">
            <Document
              file={pdfPath}
              onLoadSuccess={onDocumentLoadSuccess}
              loading={<div className="p-8">Loading PDF...</div>}
              error={<div className="p-8 text-red-500">Failed to load PDF</div>}
            >
              <Page 
                pageNumber={pageNumber} 
                renderTextLayer={false}
                renderAnnotationLayer={false}
                scale={1.2}
              />
            </Document>
          </div>

          {/* Info Panel */}
          <div className="w-80 bg-white rounded-lg border border-slate-200 p-4 h-fit">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-800">Evaluation</h3>
              <span className={`px-2 py-1 text-xs rounded-full ${
                criterion.verdict === 'ELIGIBLE' 
                  ? 'bg-green-100 text-green-700' 
                  : criterion.verdict === 'NOT_ELIGIBLE'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-amber-100 text-amber-700'
              }`}>
                {criterion.verdict}
              </span>
            </div>

            <div className="space-y-3">
              <div className="bg-slate-50 p-3 rounded-lg">
                <p className="text-xs text-slate-500">AI Confidence</p>
                <p className="font-semibold text-slate-800">{Math.round(criterion.ai_confidence * 100)}%</p>
              </div>

              {checks.length > 0 && (
                <div className="border-t border-slate-200 pt-3">
                  <p className="text-sm font-medium text-slate-700 mb-2">Verification</p>
                  {checks.map((check, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm py-1">
                      <span className={`w-2 h-2 rounded-full ${check.passed ? 'bg-green-500' : 'bg-red-500'}`}></span>
                      <span className="text-slate-600">{check.check_name}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="bg-blue-50 p-3 rounded-lg">
                <p className="text-xs text-blue-600 font-medium mb-1">AI Reasoning</p>
                <p className="text-sm text-blue-700">{criterion.reason}</p>
              </div>

              {criterion.yellow_flags && criterion.yellow_flags.length > 0 && (
                <div className="bg-amber-50 p-3 rounded-lg border border-amber-200">
                  <p className="text-xs text-amber-600 font-medium mb-1">⚠️ Yellow Flags</p>
                  {criterion.yellow_flags.map((flag, idx) => (
                    <p key={idx} className="text-xs text-amber-700">{flag.trigger_type}: {flag.reason}</p>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}