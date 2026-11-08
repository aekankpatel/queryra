import type { SampleDataset } from "../types";

const ext = { target: "_blank", rel: "noopener noreferrer" } as const;

/** "Source: <link> · via <link> · licence" for a bundled sample dataset. */
export function SampleSource({ sample }: { sample: SampleDataset }) {
  if (!sample.source) return null;
  return (
    <span className="small muted">
      Source:{" "}
      {sample.source_url ? <a href={sample.source_url} {...ext}>{sample.source}</a> : sample.source}
      {sample.via_url && <> · <a href={sample.via_url} {...ext}>{sample.id === "palmer-penguins" ? "paper" : "data files"}</a></>}
      {sample.license && <> · {sample.license}</>}
    </span>
  );
}
