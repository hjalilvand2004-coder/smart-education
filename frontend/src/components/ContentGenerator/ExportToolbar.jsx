import React from "react";

const ExportToolbar = ({
  onExportHtml,
  onExportWord,
  onExportPowerPoint,
  pptLoading = false,
}) => {
  return (
    <div className="export-toolbar">
      <span>دریافت خروجی:</span>
      <button type="button" className="export-button html" onClick={onExportHtml}>
        🌐 خروجی HTML
      </button>
      <button type="button" className="export-button word" onClick={onExportWord}>
        📄 خروجی Word
      </button>
      <button
        type="button"
        className="export-button powerpoint"
        onClick={onExportPowerPoint}
        disabled={pptLoading}
      >
        {pptLoading ? "در حال ساخت پاورپوینت..." : "📊 خروجی PowerPoint"}
      </button>
    </div>
  );
};

export default ExportToolbar;
