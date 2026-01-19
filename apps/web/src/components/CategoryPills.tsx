import { AppWindow, Briefcase, MoreHorizontal } from "lucide-react";

const categories = [
  { id: "browser-tabs", label: "Browser tab management", icon: AppWindow },
  { id: "jobs", label: "Get a job", icon: Briefcase },
  { id: "misc", label: "Miscellaneous", icon: MoreHorizontal },
];

interface CategoryPillsProps {
  activeCategory: string | null;
  onSelect: (category: string) => void;
}

export const CategoryPills = ({ activeCategory, onSelect }: CategoryPillsProps) => {
  return (
    <div className="flex flex-wrap justify-center gap-2 fade-in" style={{ animationDelay: "0.1s" }}>
      {categories.map((category) => {
        const Icon = category.icon;
        const isActive = activeCategory === category.id;
        return (
          <button
            key={category.id}
            onClick={() => onSelect(category.id)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-medium
              transition-all
              ${isActive 
                ? "bg-accent border-primary/30 text-accent-foreground" 
                : "bg-pill border-pill-border text-foreground/80 hover:bg-accent/50"
              }
            `}
          >
            <Icon className="h-4 w-4" />
            {category.label}
          </button>
        );
      })}
    </div>
  );
};
