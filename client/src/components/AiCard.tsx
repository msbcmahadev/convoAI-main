import { IconType } from "react-icons";

export default function AiCard({
  Icon,
  title,
  text,
}: {
  Icon: IconType;
  title: string;
  text: string;
}) {
  return (
    <div className="bg-white rounded-md border p-4 sm:p-3 hover:ring-1 hover:ring-slate-300 cursor-pointer transition-all">
      <Icon className="w-10 h-10 opacity-70 mb-4 text-fill sm:w-8 sm:h-8" />
      <h1 className="font-bold text-xl text-primary sm:text-lg">{title}</h1>
      <p className="text-sm opacity-95 sm:text-xs">{text}</p>
    </div>
  );
}
