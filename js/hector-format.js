// hector-format.js
// Utility functions for formatting HECTOR JSON data

function formatHector(data) {
    // Get "commodity" out of "@id": "hector:commodity/saffron"

    let type = data?.['@id'].split('/').pop().split(':')[1];
    console.log(type);
    if (type === 'commodity') {
        return formatCommodity(data);
    } else if (type === 'unit') {
        return formatUnit(data);
    } else {
        return formatJSON(data); // Default case for other types
    }
}

/**
 * Pretty-print JSON data as HTML
 * @param {Object} data - The JSON object to format
 * @returns {string} - HTML string with <pre> block
 */
function formatJSON(data) {
    return `<pre>${JSON.stringify(data, null, 2)}</pre>`;
}

/**
 * Format a commodity JSON object
 * @param {Object} commodity - HECTOR commodity object
 * @returns {string} - HTML string
 */
function formatCommodity(commodity) {
    let html = `<h3>Commodity: ${commodity.label || 'Unknown'}</h3>`;
    html += formatJSON(commodity);
    return html;
}

/**
 * Format a unit JSON object
 * @param {Object} unit - HECTOR unit object
 * @returns {string} - HTML string
 */
function formatUnit(unit) {
    let html = `<h3>Unit: ${unit.label || 'Unknown'}</h3>`;
    html += formatJSON(unit);
    return html;
}

/**
 * Append formatted JSON to the body (or any container)
 * @param {string} html - HTML string
 * @param {HTMLElement} [container=document.body] - Target container
 */
function appendFormatted(html, container = document.body) {
    const div = document.createElement('div');
    div.innerHTML = html;
    container.appendChild(div);
}
