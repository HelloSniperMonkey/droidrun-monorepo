interface Suggestion {
  id: string;
  text: string;
  category: string;
}

const suggestions: Suggestion[] = [
  // Browser tab management
  { id: "1", text: "List tabs", category: "browser-tabs" },
  { id: "2", text: "Organize tabs", category: "browser-tabs" },
  { id: "3", text: "Close old tabs", category: "browser-tabs" },
  { id: "4", text: "Merge duplicates", category: "browser-tabs" },
  { id: "5", text: "List tab sessions", category: "browser-tabs" },
  
  // Jobs
  { id: "6", text: "Find remote jobs", category: "jobs" },
  { id: "7", text: "Update my resume", category: "jobs" },
  { id: "8", text: "Search for internships", category: "jobs" },
  { id: "9", text: "Apply to saved jobs", category: "jobs" },
  
  // Miscellaneous
  { id: "10", text: "Set an alarm for tomorrow", category: "misc" },
  { id: "11", text: "Check my calendar", category: "misc" },
  { id: "12", text: "Call me at 2 AM", category: "misc" },
  { id: "13", text: "What can you do?", category: "misc" },
];

// Default suggestions to show when no category is selected (first 4)
const defaultSuggestions = [
  { id: "d1", text: "How does AI work?", category: "default" },
  { id: "d2", text: "Are black holes real?", category: "default" },
  { id: "d3", text: 'How many Rs are in the word "strawberry"?', category: "default" },
  { id: "d4", text: "What is the meaning of life?", category: "default" },
];

interface SuggestionsListProps {
  onSelect: (suggestion: string) => void;
  activeCategory: string | null;
}

export const SuggestionsList = ({ onSelect, activeCategory }: SuggestionsListProps) => {
  // If no category selected, show default 4 suggestions
  // If category selected, show all suggestions for that category
  const displaySuggestions = activeCategory
    ? suggestions.filter((s) => s.category === activeCategory)
    : defaultSuggestions;

  return (
    <div className="w-full max-w-xl mx-auto fade-in" style={{ animationDelay: "0.2s" }}>
      <div className="flex flex-col">
        {displaySuggestions.map((suggestion, index) => (
          <button
            key={suggestion.id}
            onClick={() => onSelect(suggestion.text)}
            className={`
              w-full text-left py-4 px-2 text-foreground/80 hover:text-foreground 
              suggestion-item transition-colors
              ${index < displaySuggestions.length - 1 ? "border-b border-border/30" : ""}
            `}
          >
            {suggestion.text}
          </button>
        ))}
      </div>
    </div>
  );
};
