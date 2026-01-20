import { cn } from "@/lib/utils";

interface ModeToggleProps {
  mode: "local" | "cloud";
  onChange: (mode: "local" | "cloud") => void;
  className?: string;
}

export const ModeToggle = ({ mode, onChange, className }: ModeToggleProps) => {
  const isLocal = mode === "local";

  return (
    <button
      onClick={() => onChange(isLocal ? "cloud" : "local")}
      className={cn(
        "group relative flex w-full items-center rounded-lg border-2 border-border/20 bg-black/20 p-1",
        "transition-all duration-300 hover:border-border/40",
        "h-10 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
        className
      )}
      type="button"
      aria-label="Toggle execution mode"
    >
      {/* Sliding Highlighter */}
      <div
        className={cn(
          "absolute inset-y-1 left-1 w-[calc(50%-4px)] rounded-md bg-primary shadow-sm transition-transform duration-300 ease-spring",
          !isLocal && "translate-x-[calc(100%+4px)]"
        )}
      />

      {/* Local Label */}
      <span
        className={cn(
          "relative z-10 flex-1 text-center text-xs font-bold uppercase tracking-wider transition-colors duration-300",
          isLocal ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground"
        )}
      >
        Local
      </span>

      {/* Cloud Label */}
      <span
        className={cn(
          "relative z-10 flex-1 text-center text-xs font-bold uppercase tracking-wider transition-colors duration-300",
          !isLocal ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground"
        )}
      >
        Cloud
      </span>
    </button>
  );
};
