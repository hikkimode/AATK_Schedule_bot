"use client";

export default function ScheduleSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-4">
      {Array.from({ length: 5 }).map((_, index) => (
        <div
          key={index}
          className="rounded-lg p-4 animate-pulse"
          style={{ backgroundColor: "var(--tg-theme-secondary-bg-color, #2d2d2d)" }}
        >
          <div className="flex items-center gap-3">
            {/* Short block - lesson number */}
            <div
              className="h-6 w-12 rounded"
              style={{ backgroundColor: "var(--tg-theme-hint-color, #6b7280)" }}
            />
            
            {/* Long block - subject name */}
            <div
              className="h-6 flex-1 rounded"
              style={{ backgroundColor: "var(--tg-theme-hint-color, #6b7280)" }}
            />
            
            {/* Medium block - room */}
            <div
              className="h-6 w-20 rounded"
              style={{ backgroundColor: "var(--tg-theme-hint-color, #6b7280)" }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
