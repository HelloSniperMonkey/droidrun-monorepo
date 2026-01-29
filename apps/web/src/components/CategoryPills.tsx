import { AppWindow, Briefcase, MoreHorizontal } from "lucide-react";

const categories = [
  { id: "browser-tabs", label: "Browser", icon: AppWindow },
  { id: "jobs", label: "Career", icon: Briefcase },
  { id: "misc", label: "Device", icon: MoreHorizontal },
];

interface CategoryPillsProps {
  activeCategory: string | null;
  onSelect: (category: string) => void;
}

export const CategoryPills = ({ activeCategory, onSelect }: CategoryPillsProps) => {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {categories.map((category) => {
        const Icon = category.icon;
        const isActive = activeCategory === category.id;
        return (
          <button
            key={category.id}
            onClick={() => onSelect(category.id)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest
              transition-all duration-300 active:scale-95
              ${isActive
                ? "bg-brand-pink text-white shadow-lg shadow-brand-pink/20"
                : "bg-transparent text-white/30 hover:text-white/60 hover:bg-white/5"
              }
            `}
          >
            <Icon className="h-3.5 w-3.5" />
            {category.label}
          </button>
        );
      })}
    </div>
  );
};
