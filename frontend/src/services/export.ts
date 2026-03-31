// Master export service for Bloomberg Data Fabric terminal

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function exportToCSV(data: Record<string, unknown>[], filename: string): void {
  if (!data.length) return;
  const headers = Object.keys(data[0]!);
  const escape = (val: unknown): string => {
    const str = val == null ? '' : String(val);
    return str.includes(',') || str.includes('"') || str.includes('\n')
      ? `"${str.replace(/"/g, '""')}"`
      : str;
  };
  const rows = [
    headers.map(escape).join(','),
    ...data.map(row => headers.map(h => escape(row[h])).join(',')),
  ];
  const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(blob, filename.endsWith('.csv') ? filename : `${filename}.csv`);
}

export function exportToJSON(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  triggerDownload(blob, filename.endsWith('.json') ? filename : `${filename}.json`);
}

export async function exportChartToPNG(svgElement: SVGElement, filename: string): Promise<void> {
  const scale = 2;
  const bbox = svgElement.getBoundingClientRect();
  const width = bbox.width * scale;
  const height = bbox.height * scale;

  const svgData = new XMLSerializer().serializeToString(svgElement);
  const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) { reject(new Error('Canvas 2D context unavailable')); return; }
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      canvas.toBlob(blob => {
        if (!blob) { reject(new Error('Canvas toBlob failed')); return; }
        triggerDownload(blob, filename.endsWith('.png') ? filename : `${filename}.png`);
        resolve();
      }, 'image/png');
    };
    img.onerror = reject;
    img.src = url;
  });
}

export function exportChartToSVG(svgElement: SVGElement, filename: string): void {
  const svgData = new XMLSerializer().serializeToString(svgElement);
  const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
  triggerDownload(blob, filename.endsWith('.svg') ? filename : `${filename}.svg`);
}

export function exportTableToXLSX(
  data: Record<string, unknown>[],
  headers: Record<string, string>,
  filename: string,
): void {
  if (!data.length) return;
  const keys = Object.keys(headers);
  const headerRow = keys.map(k => headers[k]).join('\t');
  const dataRows = data.map(row => keys.map(k => {
    const val = row[k];
    return val == null ? '' : String(val);
  }).join('\t'));
  const tsv = [headerRow, ...dataRows].join('\n');
  const blob = new Blob([tsv], { type: 'application/vnd.ms-excel' });
  triggerDownload(blob, filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`);
}
