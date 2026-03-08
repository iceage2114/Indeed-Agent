// Header.jsx — App title and job count banner

export default function Header({ total, filtered, onWipe, onViewMatches }) {
  return (
    <header className="bg-blue-700 text-white px-6 py-4 shadow-md">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">Indeed Job Board</h1>
          <button
            onClick={onViewMatches}
            className="text-sm bg-blue-500 hover:bg-blue-400 text-white rounded-md px-3 py-1 transition-colors font-medium"
          >
            Top Matches ✦
          </button>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm bg-blue-600 rounded-full px-3 py-1">
            {filtered === total
              ? `${total} job${total !== 1 ? "s" : ""} found`
              : `${filtered} of ${total} jobs`}
          </span>
          <button
            onClick={onWipe}
            className="text-sm bg-red-600 hover:bg-red-500 text-white rounded-md px-3 py-1 transition-colors"
          >
            Wipe DB
          </button>
        </div>
      </div>
    </header>
  );
}
