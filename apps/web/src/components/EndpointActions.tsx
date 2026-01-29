import { ChevronRight } from "lucide-react";
import { ReactNode } from "react";

export interface EndpointAction {
  id: string;
  label: ReactNode;
  labelText: string; // Plain text version for callbacks
  description?: string;
  category: string;
  onRun: () => Promise<any>;
}

interface EndpointActionsProps {
  actions: EndpointAction[];
  activeCategory: string | null;
  onResult: (label: string, result: any) => void;
  onStart?: (action: EndpointAction) => void;
}

export const EndpointActions = ({ actions, activeCategory, onResult, onStart }: EndpointActionsProps) => {
  const handleRun = async (action: EndpointAction) => {
    onStart?.(action);
    try {
      const result = await action.onRun();
      onResult(action.labelText, result);
    } catch (err: any) {
      onResult(action.labelText, { error: err?.message || "Request failed" });
    }
  };

  const displayActions = activeCategory
    ? actions.filter((action) => action.category === activeCategory)
    : actions.slice(0, 4);

  if (displayActions.length === 0) return null;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {displayActions.map((action) => (
          <button
            key={action.id}
            onClick={() => handleRun(action)}
            className="flex items-center justify-between p-4 rounded-xl bg-white/[0.03] border border-white/5 hover:border-brand-pink/50 hover:bg-white/[0.05] transition-all group group-hover:shadow-[0_0_20px_rgba(255,46,144,0.1)]"
          >
            <div className="text-left">
              <span className="block text-xs font-bold text-white/80 group-hover:text-white uppercase tracking-tight">
                {action.label}
              </span>
              <span className="block text-[8px] font-black text-white/20 uppercase tracking-[0.2em] mt-1">
                {action.category.replace('-', ' ')}
              </span>
            </div>
            <ChevronRight className="h-4 w-4 text-white/10 group-hover:text-brand-pink group-hover:translate-x-0.5 transition-all" />
          </button>
        ))}
      </div>
    </div>
  );
};
