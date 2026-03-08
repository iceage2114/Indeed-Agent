// TopMatchesPage.jsx — displays the top job matches from the job_matcher report

import { useState, useEffect } from "react";

function MatchCard({ rank, job }) {
  const score = typeof job.similarity_score === "number"
    ? (job.similarity_score * 100).toFixed(1) + "%"
    : "N/A";

  const scoreNum = typeof job.similarity_score === "number" ? job.similarity_score : 0;
  const barColor = scoreNum >= 0.6 ? "bg-green-500" : scoreNum >= 0.4 ? "bg-yellow-400" : "bg-red-400";
  const barWidth = Math.round(scoreNum * 100);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">#{rank}</span>
            {job.easy_apply && (
              <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">Easy Apply</span>
            )}
          </div>
          <h3 className="text-base font-semibold text-gray-900 truncate">{job.title}</h3>
          <p className="text-sm text-gray-500">{job.company} &mdash; {job.location}</p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold text-blue-600">{score}</div>
          <div className="text-xs text-gray-400">similarity</div>
        </div>
      </div>

      {/* Similarity bar */}
      <div className="w-full bg-gray-100 rounded-full h-1.5">
        <div className={`${barColor} h-1.5 rounded-full`} style={{ width: `${barWidth}%` }} />
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
        {job.field && <span><span className="font-medium">Field:</span> {job.field}</span>}
        {job.date_posted && <span><span className="font-medium">Posted:</span> {job.date_posted}</span>}
      </div>

      {job.description && (
        <p className="text-sm text-gray-600 line-clamp-3">
          {job.description.slice(0, 300)}{job.description.length > 300 ? "…" : ""}
        </p>
      )}

      {job.url && (
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline self-start"
        >
          View on Indeed →
        </a>
      )}
    </div>
  );
}

export default function TopMatchesPage({ onBack }) {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch("/api/matches")
      .then((r) => r.json())
      .then((data) => {
        if (data.error) setError(data.error);
        else setMatches(data.matches || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Page header */}
      <header className="bg-blue-700 text-white px-6 py-4 shadow-md">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-md px-3 py-1 transition-colors"
            >
              ← Back
            </button>
            <h1 className="text-2xl font-bold tracking-tight">Top Job Matches</h1>
          </div>
          {!loading && !error && (
            <span className="text-sm bg-blue-600 rounded-full px-3 py-1">
              {matches.length} match{matches.length !== 1 ? "es" : ""}
            </span>
          )}
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {loading && (
          <div className="text-center text-gray-500 py-20 text-lg">Loading matches…</div>
        )}

        {!loading && error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-6 text-center">
            <p className="font-semibold mb-1">Could not load matches</p>
            <p className="text-sm">{error}</p>
            <p className="text-sm mt-3 text-gray-500">Run <code className="bg-gray-100 px-1 rounded">python main.py</code> inside the <code className="bg-gray-100 px-1 rounded">job_matcher</code> folder first.</p>
          </div>
        )}

        {!loading && !error && matches.length === 0 && (
          <div className="text-center text-gray-400 py-20">No matches found in the report.</div>
        )}

        {!loading && !error && matches.length > 0 && (
          <div className="flex flex-col gap-4">
            {matches.map((job, i) => (
              <MatchCard key={job.id ?? i} rank={i + 1} job={job} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
