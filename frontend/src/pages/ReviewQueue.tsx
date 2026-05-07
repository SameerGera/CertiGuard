import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import type { VerdictOutput } from '../types/api'
import { getReviewQueue, getTenderDetail, type TenderDetail } from '../hooks/useApi'
import BidderCard from '../components/BidderCard'
import YellowFlagBadge from '../components/YellowFlagBadge'

interface ReviewQueueProps {
  tenderId: string
}

export default function ReviewQueue({ tenderId }: ReviewQueueProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [data, setData] = useState<VerdictOutput | null>(null)
  const [tenderDetail, setTenderDetail] = useState<TenderDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'ALL' | 'NEEDS_REVIEW' | 'ELIGIBLE' | 'NOT_ELIGIBLE'>('ALL')
  const [search, setSearch] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (!tenderId) {
      setLoading(false)
      return
    }
    setLoading(true)
    
    // Fetch both tender detail and review queue
    Promise.all([
      getTenderDetail(tenderId),
      getReviewQueue(tenderId)
    ])
      .then(([detail, queue]) => {
        setTenderDetail(detail)
        setData(queue)
      })
      .catch(err => {
        console.error('Failed to fetch data:', err)
        getReviewQueue(tenderId).then(setData).catch(console.error)
      })
      .finally(() => setLoading(false))
  }, [tenderId, refreshKey])

  // Refresh when returning from override
  useEffect(() => {
    if (location.state?.refresh) {
      setRefreshKey(k => k + 1)
      navigate(location.pathname, { replace: true, state: {} })
    }
  }, [location])

  const filteredBidders = data?.bidders.filter((b) => {
    const matchesFilter = filter === 'ALL' || b.overall_verdict === filter
    const matchesSearch = b.bidder_name.toLowerCase().includes(search.toLowerCase())
    return matchesFilter && matchesSearch
  }) || []

  if (!tenderId) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Select a tender from the Dashboard to view the review queue.</p>
      </div>
    )
  }

  if (loading) {
    return <div className="text-center py-12 text-slate-500">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Review Queue</h2>
        <p className="text-slate-500">{data?.tender_name}</p>
      </div>

      {/* Tender Criteria Section */}
      {tenderDetail?.criteria && tenderDetail.criteria.length > 0 && (
        <div className="bg-blue-50 rounded-xl border border-blue-200 p-4">
          <h3 className="font-semibold text-blue-800 mb-3">Tender Eligibility Criteria</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {tenderDetail.criteria.map((criterion) => (
              <div key={criterion.id} className="bg-white rounded-lg p-3 border border-blue-100">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-slate-500">{criterion.id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    criterion.nature === 'MANDATORY' 
                      ? 'bg-red-100 text-red-700' 
                      : 'bg-green-100 text-green-700'
                  }`}>
                    {criterion.nature}
                  </span>
                </div>
                <p className="text-sm font-medium text-slate-800">{criterion.label}</p>
                <span className="text-xs text-slate-500">{criterion.type}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-4 items-center">
        <input
          type="text"
          placeholder="Search bidders..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as typeof filter)}
          className="px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="ALL">All</option>
          <option value="NEEDS_REVIEW">Needs Review</option>
          <option value="ELIGIBLE">Eligible</option>
          <option value="NOT_ELIGIBLE">Not Eligible</option>
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200">
        <div className="p-4 border-b border-slate-200 flex justify-between items-center">
          <span className="text-sm text-slate-600">{filteredBidders.length} bidders</span>
          {data?.yellow_flag_summary.total ? (
            <YellowFlagBadge count={data.yellow_flag_summary.total} />
          ) : null}
        </div>
        <div className="divide-y divide-slate-100">
          {filteredBidders.map((bidder) => (
            <div
              key={bidder.bidder_id}
              onClick={() => navigate(`/review/${bidder.bidder_id}`)}
              className="p-4 hover:bg-slate-50 cursor-pointer"
            >
              <BidderCard bidder={bidder} />
            </div>
          ))}
        </div>
        {filteredBidders.length === 0 && (
          <div className="p-8 text-center text-slate-500">No bidders found</div>
        )}
      </div>
    </div>
  )
}