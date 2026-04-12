import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

/**
 * Export a report to a professional PDF matching the approved mockup design.
 *
 * Layout:  Header bar  Title + metadata  Summary  Charts (if any)  Data table  Footer
 * Colors:  Navy blue (#182e58) for accents, slate grays for body text.
 * Table:   Alternating rows, navy column headers with white text.
 *          Capped at 50 rows with a note if data is larger.
 *
 * This is ASYNC because we use html2canvas to capture chart DOM elements.
 */
export async function exportReportToPdf({ report, reportData }) {
    const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const pageW = doc.internal.pageSize.getWidth();   // 210
    const pageH = doc.internal.pageSize.getHeight();  // 297
    const marginL = 18;
    const marginR = 18;
    const contentW = pageW - marginL - marginR;

    // -- Colors ---------------------------------------------------------------
    const navy = [24, 46, 88];     // #182e58
    const dark = [30, 41, 59];     // slate-800
    const gray = [100, 116, 139];  // slate-500
    const lightGray = [241, 245, 249]; // slate-100
    const white = [255, 255, 255];
    const divider = [203, 213, 225];  // slate-300

    let y = 0;

    // -- 1. Header Bar --------------------------------------------------------
    doc.setFillColor(...navy);
    doc.rect(0, 0, pageW, 12, 'F');

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(9);
    doc.setTextColor(...white);
    doc.text('ANALYTICS REPORT', marginL, 8);

    // Logo  small circle on right
    const logoX = pageW - marginR - 4;
    doc.setFillColor(...white);
    doc.circle(logoX, 6, 3.5, 'F');
    doc.setFontSize(6);
    doc.setTextColor(...navy);
    doc.text('A', logoX - 1.5, 7.5);

    y = 22;

    // -- 2. Title -------------------------------------------------------------
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(18);
    doc.setTextColor(...dark);

    const titleLines = doc.splitTextToSize(report.title || 'Untitled Report', contentW);
    doc.text(titleLines, marginL, y);
    y += titleLines.length * 8 + 2;

    // Metadata line
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    const rowCount = reportData?.data?.length || report.rowCount || 0;
    const metaText = `Generated: ${dateStr}  |  Rows: ${rowCount}`;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(...gray);
    doc.text(metaText, marginL, y);
    y += 8;

    // Divider
    doc.setDrawColor(...divider);
    doc.setLineWidth(0.3);
    doc.line(marginL, y, pageW - marginR, y);
    y += 6;

    // -- 3. Summary Section ---------------------------------------------------
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(9);
    doc.setTextColor(...navy);
    doc.text('SUMMARY', marginL, y);
    y += 5;

    const rawSummary = report.detailed_summary || report.summary || 'No summary available.';
    const cleanSummary = rawSummary
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/^[--]\s*/gm, '  -  ')
        .replace(/^#+\s*/gm, '')
        .replace(/\n{3,}/g, '\n\n');

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(...dark);

    const summaryLines = doc.splitTextToSize(cleanSummary, contentW);
    const maxSummaryLines = 20;
    const displaySummary = summaryLines.slice(0, maxSummaryLines);
    doc.text(displaySummary, marginL, y);
    y += displaySummary.length * 3.8 + 4;

    // Divider
    doc.setDrawColor(...divider);
    doc.line(marginL, y, pageW - marginR, y);
    y += 6;

    // -- 4. Charts (captured from DOM) ----------------------------------------
    const chartImages = await captureCharts();

    if (chartImages.length > 0) {
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.setTextColor(...navy);
        doc.text('CHARTS', marginL, y);
        y += 5;

        for (const chartImg of chartImages) {
            const imgW = contentW;
            // Maintain aspect ratio
            const imgH = (chartImg.height / chartImg.width) * imgW;

            // Check page break
            if (y + imgH > pageH - 15) {
                drawFooter(doc, pageW, pageH, marginL, marginR, navy, gray);
                doc.addPage();
                y = 15;
            }

            doc.addImage(chartImg.dataUrl, 'PNG', marginL, y, imgW, imgH);
            y += imgH + 5;
        }

        // Divider after charts
        if (y + 6 > pageH - 15) {
            drawFooter(doc, pageW, pageH, marginL, marginR, navy, gray);
            doc.addPage();
            y = 15;
        }
        doc.setDrawColor(...divider);
        doc.line(marginL, y, pageW - marginR, y);
        y += 6;
    }

    // -- 5. Data Table --------------------------------------------------------
    const columns = reportData?.columns || report.columns || [];
    const allRows = reportData?.data || [];
    const maxTableRows = 50;
    const tableRows = allRows.slice(0, maxTableRows);
    const showTruncationNote = allRows.length > maxTableRows;

    if (columns.length > 0 && tableRows.length > 0) {
        const headingText = showTruncationNote
            ? `DATA (showing ${maxTableRows} of ${allRows.length} rows)`
            : `DATA (${allRows.length} rows)`;
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.setTextColor(...navy);
        doc.text(headingText, marginL, y);
        y += 5;

        const maxCols = Math.min(columns.length, 8);
        const displayCols = columns.slice(0, maxCols);
        const colW = contentW / displayCols.length;
        const rowH = 6;

        const checkPageBreak = (neededH) => {
            if (y + neededH > pageH - 15) {
                drawFooter(doc, pageW, pageH, marginL, marginR, navy, gray);
                doc.addPage();
                y = 15;
                return true;
            }
            return false;
        };

        // Table Header
        checkPageBreak(rowH);
        doc.setFillColor(...navy);
        doc.rect(marginL, y - 4, contentW, rowH, 'F');
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(7);
        doc.setTextColor(...white);

        displayCols.forEach((col, i) => {
            const cellX = marginL + i * colW + 1.5;
            const label = formatColumnHeader(col);
            doc.text(label, cellX, y, { maxWidth: colW - 3 });
        });
        y += rowH - 1;

        // Table Rows
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(7);

        tableRows.forEach((row, rowIdx) => {
            checkPageBreak(rowH);

            if (rowIdx % 2 === 0) {
                doc.setFillColor(...lightGray);
                doc.rect(marginL, y - 3.5, contentW, rowH, 'F');
            }

            doc.setTextColor(...dark);
            displayCols.forEach((col, i) => {
                const cellX = marginL + i * colW + 1.5;
                let val = row[col];
                if (val === null || val === undefined) val = '';
                val = String(val);
                if (val.length > 22) val = val.substring(0, 20) + '';
                doc.text(val, cellX, y, { maxWidth: colW - 3 });
            });
            y += rowH;
        });

        if (showTruncationNote) {
            y += 3;
            doc.setFont('helvetica', 'italic');
            doc.setFontSize(7);
            doc.setTextColor(...gray);
            doc.text(
                `Full dataset contains ${allRows.length} rows. Export CSV for complete data.`,
                marginL, y
            );
        }
    }

    // -- 6. Footer ------------------------------------------------------------
    drawFooter(doc, pageW, pageH, marginL, marginR, navy, gray);

    // -- Save -----------------------------------------------------------------
    const safeName = (report.title || 'report')
        .replace(/[^a-zA-Z0-9]/g, '_')
        .replace(/_+/g, '_')
        .substring(0, 60);
    doc.save(`${safeName}.pdf`);
}


// -- Chart Capture via html2canvas --------------------------------------------

async function captureCharts() {
    const container = document.getElementById('pdf-chart-container');
    if (!container) return [];

    // Save original inline style so we can restore it after capture
    const originalStyle = container.getAttribute('style') || '';

    // Temporarily make the container visible with real dimensions so that
    // Recharts' ResponsiveContainer can calculate width and render SVGs.
    // We place it off-screen vertically (below the fold) so the user doesn't
    // see a flash, but it still has a real layout width.
    container.setAttribute('style',
        'position:fixed; left:0; top:100vh; width:100vw; z-index:-1; opacity:1; pointer-events:none;'
    );

    // Wait for Recharts to measure and render
    await new Promise(resolve => setTimeout(resolve, 800));

    // Verify charts actually rendered
    const hasCharts = container.querySelector('.recharts-responsive-container svg');
    if (!hasCharts) {
        container.setAttribute('style', originalStyle);
        return [];
    }

    try {
        const canvas = await html2canvas(container, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff',
            logging: false,
            ignoreElements: (element) => {
                return element.tagName === 'BUTTON' || element.classList?.contains('tooltip');
            }
        });

        // Restore hidden state
        container.setAttribute('style', originalStyle);

        return [{
            dataUrl: canvas.toDataURL('image/png'),
            width: canvas.width,
            height: canvas.height
        }];
    } catch (err) {
        console.warn('Failed to capture charts:', err);
        container.setAttribute('style', originalStyle);
        return [];
    }
}


// -- Helpers ------------------------------------------------------------------

function drawFooter(doc, pageW, pageH, marginL, marginR, navy, gray) {
    const footerY = pageH - 10;
    doc.setDrawColor(...navy);
    doc.setLineWidth(0.3);
    doc.line(marginL, footerY, pageW - marginR, footerY);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(6.5);
    doc.setTextColor(...gray);

    const pages = doc.internal.getNumberOfPages();
    const currentPage = doc.internal.getCurrentPageInfo().pageNumber;
    doc.text(
        `Confidential  Generated by Analytics Platform  Page ${currentPage} of ${pages}`,
        pageW / 2, footerY + 4,
        { align: 'center' }
    );
}

function formatColumnHeader(col) {
    return col
        .replace(/_/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .split(' ')
        .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
        .join(' ');
}
