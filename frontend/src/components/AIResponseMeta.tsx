import { Cpu, Wrench } from "lucide-react";
import { Badge } from "./ui";

export function AIResponseMeta({
  meta,
}: {
  meta: Record<string, unknown>;
}) {
  const model = typeof meta.model === "string" ? meta.model : "";
  const tool = typeof meta.tool === "string" ? meta.tool : "";
  if (!model && !tool) return null;

  return (
    <div
      role="group"
      aria-label="AI response provenance"
      className="flex flex-wrap gap-2"
    >
      {model && (
        <Badge className="max-w-full gap-1.5 border-[#b9f55b]/25 bg-[#b9f55b]/10 text-[#e1ffb5]">
          <Cpu aria-hidden="true" size={13} />
          <span className="text-[#8fa19b]">Model</span>
          <span className="break-all font-mono text-[11px]">{model}</span>
        </Badge>
      )}
      {tool && (
        <Badge className="max-w-full gap-1.5 border-[#49dcb1]/25 bg-[#49dcb1]/10 text-[#9bf4da]">
          <Wrench aria-hidden="true" size={13} />
          <span className="text-[#8fa19b]">Tool</span>
          <span className="break-all font-mono text-[11px]">{tool}</span>
        </Badge>
      )}
    </div>
  );
}
