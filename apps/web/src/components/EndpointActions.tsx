export interface EndpointAction {
  id: string;
  label: string;
  description?: string;
  category: string;
  onRun: () => Promise<any>;
}

interface EndpointActionsProps {
  actions: EndpointAction[];
  activeCategory: string | null;
  onResult: (label: string, result: any) => void;
}

export const EndpointActions = ({ actions, activeCategory, onResult }: EndpointActionsProps) => {
  const handleRun = async (action: EndpointAction) => {
    try {
      const result = await action.onRun();
      onResult(action.label, result);
    } catch (err: any) {
      onResult(action.label, { error: err?.message || "Request failed" });
    }
  };

  // If category is selected, show all actions for that category
  // If no category selected, show first 4 actions as defaults
  const displayActions = activeCategory
    ? actions.filter((action) => action.category === activeCategory)
    : actions.slice(0, 4);

  if (displayActions.length === 0) {
    return null;
  }

  return (
    <div className="w-full max-w-xl mx-auto fade-in" style={{ animationDelay: "0.2s" }}>
      <div className="flex flex-col">
        {displayActions.map((action, index) => (
          <button
            key={action.id}
            onClick={() => handleRun(action)}
            className={`
              w-full text-left py-4 px-2 text-foreground/80 hover:text-foreground 
              suggestion-item transition-colors cursor-pointer
              ${index < displayActions.length - 1 ? "border-b border-border/30" : ""}
            `}
          >
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
};
