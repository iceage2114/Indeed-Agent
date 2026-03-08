// JobCard.jsx � Single job display with expand/collapse description

import { useState } from "react";

const FIELD_COLORS = {
  "entry level software engineering": "bg-blue-100 text-blue-800",
  "entry level cybersecurity": "bg-green-100 text-green-800",
  "IT technician": "bg-orange-100 text-orange-800",
};

export default function JobCard({ job, onApply, onDismiss }) {
  const [expanded, setExpanded] = useState(false);

  const colorClass =
    FIELD_COLORS[job.field?.toLowerCase()] ||
    FIELD_COLORS[Object.keys(FIELD_COLORS).find((k) =>
      job.field?.toLowerCase().includes(k.toLowerCase())
    )] ||
    "bg-gray-100 text-gray-800";

  const descLimit = 200;
  const desc = job.description || "";
  const isLong = desc.length > descLimit;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 flex flex-col gap-3 hover:shadow-md transition-shadow">
      {/* Title */}
      <h2 className="text-base font-semibold text-gray-900 leading-snug">
        {job.title}
      </h2>

      {/* Company + Location */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500">
        <span className="font-medium text-gray-700">{job.company}</span>
        <span className="text-gray-300">|</span>
        <span>{job.location}</span>
      </div>

      {/* Field tag */}
      <span
        className={`inline-block self-start text-xs font-semibold rounded-full px-2.5 py-0.5 ${colorClass}`}
      >
        {job.field}
      </span>

      {/* Description */}
      <p className="text-sm text-gray-600 leading-relaxed">
        {expanded || !isLong ? desc : `${desc.slice(0, descLimit)}...`}
      </p>

      {/* Footer row */}
      <div className="flex items-center justify-between mt-auto pt-2 border-t border-gray-100">
        <div className="flex items-center gap-3">
          {isLong && (
            <button
              className="text-xs text-blue-600 hover:underline"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
          {job.date_posted && (
            <span className="text-xs text-gray-400">{job.date_posted}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Mark as applied */}
          <button
            onClick={() => onApply && onApply(job)}
            title="Mark as applied"
            className="w-8 h-8 rounded-full bg-green-500 hover:bg-green-600 text-white flex items-center justify-center text-xl font-bold transition-colors pb-0.5"
          >
            +
          </button>
          {/* Dismiss */}
          <button
            onClick={() => onDismiss && onDismiss(job.id)}
            title="Dismiss job"
            className="w-7 h-7 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center text-sm font-bold transition-colors"
          >
            ✕
          </button>
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-colors"
          >
            View on Indeed
          </a>
        </div>
      </div>
    </div>
  );
}
