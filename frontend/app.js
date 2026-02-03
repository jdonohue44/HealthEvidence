/**
 * Ultra-Significant Trials
 * Frontend application for displaying and filtering clinical trial data
 */

// State
let goldStandardStudies = [];
let weakEvidenceStudies = [];
let currentTab = 'latest';
let searchQuery = '';

// DOM Elements
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const emptyStateEl = document.getElementById('empty-state');
const studiesListEl = document.getElementById('studies-list');
const modalEl = document.getElementById('study-modal');
const modalBodyEl = modalEl.querySelector('.modal-body');
const modalBackdropEl = modalEl.querySelector('.modal-backdrop');
const modalCloseEl = modalEl.querySelector('.modal-close');
const searchInputEl = document.getElementById('search-input');

/**
 * Initialize the application
 */
async function init() {
    try {
        // Load both data sources in parallel
        const [goldData, weakData] = await Promise.all([
            loadCSV('data/trials.csv'),
            loadCSV('data/weak_evidence.csv')
        ]);
        
        goldStandardStudies = processGoldStandardData(goldData);
        weakEvidenceStudies = processWeakEvidenceData(weakData);
        
        // Set up event listeners
        setupTabNavigation();
        setupSearch();
        setupModal();
        
        // Render initial view
        renderStudies();
        
    } catch (error) {
        console.error('Failed to initialize:', error);
        showError();
    }
}

/**
 * Load and parse a CSV file
 */
function loadCSV(path) {
    return new Promise((resolve, reject) => {
        Papa.parse(path, {
            download: true,
            header: true,
            skipEmptyLines: true,
            complete: (results) => {
                if (results.errors.length > 0) {
                    console.warn('CSV parse warnings:', results.errors);
                }
                resolve(results.data);
            },
            error: (error) => {
                reject(error);
            }
        });
    });
}

/**
 * Process gold standard trial data
 */
function processGoldStandardData(data) {
    return data
        .filter(row => row.nct_id && row.headline)
        .map(row => ({
            id: row.nct_id,
            type: 'gold',
            category: (row.category || 'health').toLowerCase(),
            evidenceTier: row.evidence_tier || 'GOLD',
            title: row.title || '',
            headline: row.headline || '',
            summary: row.summary || '',
            intervention: row.intervention || '',
            interventionDescription: row.intervention_description || '',
            comparator: row.comparator || '',
            population: row.population || '',
            conditions: row.conditions || '',
            sampleSize: parseInt(row.sample_size) || 0,
            studyEnrollment: parseInt(row.study_enrollment) || parseInt(row.sample_size) || 0,
            sampleSizeCategory: row.sample_size_category || '',
            numArms: parseInt(row.num_arms) || 2,
            completionDate: row.completion_date || '',
            outcomeName: row.outcome_name || '',
            outcomeType: row.outcome_type || '',
            controlMean: parseFloat(row.control_mean) || null,
            treatmentMean: parseFloat(row.treatment_mean) || null,
            effectSize: parseFloat(row.effect_size) || null,
            effectMagnitude: row.effect_magnitude || '',
            pValue: parseFloat(row.p_value) || null,
            ultraScore: parseFloat(row.ultra_score) || 0,
            sourceUrl: `https://clinicaltrials.gov/study/${row.nct_id}`
        }))
        .sort((a, b) => b.ultraScore - a.ultraScore);
}

/**
 * Process weak evidence data
 */
function processWeakEvidenceData(data) {
    return data
        .filter(row => row.claim || row.headline)
        .map(row => ({
            id: row.study_id || `weak-${Math.random().toString(36).substr(2, 9)}`,
            type: 'weak',
            category: (row.category || 'health').toLowerCase(),
            evidenceTier: 'WEAK',
            headline: row.headline || row.claim || '',
            claim: row.claim || '',
            actualFinding: row.actual_finding || '',
            summary: row.summary || '',
            studyType: row.study_type || 'Observational',
            sampleSize: parseInt(row.sample_size) || 0,
            whyWeak: row.why_weak || '',
            confounders: row.confounders || '',
            sourceUrl: row.source_url || '',
            datePublished: row.date_published || ''
        }));
}

/**
 * Set up tab navigation
 */
function setupTabNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Update active state
            tabs.forEach(t => {
                t.classList.remove('active');
                t.setAttribute('aria-selected', 'false');
            });
            tab.classList.add('active');
            tab.setAttribute('aria-selected', 'true');
            
            // Update current tab and render
            currentTab = tab.dataset.tab;
            
            // Clear search when switching tabs
            searchQuery = '';
            if (searchInputEl) {
                searchInputEl.value = '';
            }
            
            renderStudies();
        });
    });
}

/**
 * Set up search functionality
 */
function setupSearch() {
    if (!searchInputEl) return;
    
    // Debounce search input
    let searchTimeout;
    
    searchInputEl.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        
        searchTimeout = setTimeout(() => {
            searchQuery = e.target.value.trim().toLowerCase();
            renderStudies();
        }, 200); // 200ms debounce
    });
    
    // Handle Enter key
    searchInputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            clearTimeout(searchTimeout);
            searchQuery = e.target.value.trim().toLowerCase();
            renderStudies();
        }
    });
}

/**
 * Set up modal functionality
 */
function setupModal() {
    modalCloseEl.addEventListener('click', closeModal);
    modalBackdropEl.addEventListener('click', closeModal);
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalEl.style.display !== 'none') {
            closeModal();
        }
    });
}

/**
 * Check if a study matches the search query
 */
function matchesSearch(study, query) {
    if (!query) return true;
    
    // Fields to search in
    const searchableFields = [
        study.headline,
        study.summary,
        study.title,
        study.intervention,
        study.interventionDescription,
        study.conditions,
        study.population,
        study.outcomeName,
        study.category,
        // For weak evidence
        study.claim,
        study.actualFinding,
        study.whyWeak,
        study.confounders
    ];
    
    // Check if any field contains the search query
    return searchableFields.some(field => 
        field && field.toLowerCase().includes(query)
    );
}

/**
 * Get studies filtered by current tab and search query
 */
function getFilteredStudies() {
    let studies;
    
    // First filter by tab
    if (currentTab === 'weak') {
        studies = weakEvidenceStudies;
    } else if (currentTab === 'latest') {
        studies = goldStandardStudies.slice(0, 20);
    } else {
        studies = goldStandardStudies.filter(s => s.category === currentTab);
    }
    
    // If there's a search query, search across ALL studies (both gold and weak)
    if (searchQuery) {
        // Combine all studies and filter by search
        const allStudies = [...goldStandardStudies, ...weakEvidenceStudies];
        studies = allStudies.filter(s => matchesSearch(s, searchQuery));
    }
    
    return studies;
}

/**
 * Render the studies list
 */
function renderStudies() {
    const studies = getFilteredStudies();
    
    // Hide loading
    loadingEl.style.display = 'none';
    
    if (studies.length === 0) {
        studiesListEl.innerHTML = '';
        emptyStateEl.style.display = 'block';
        
        // Update empty state message based on context
        const emptyMessageEl = document.getElementById('empty-state-message');
        if (emptyMessageEl) {
            if (searchQuery) {
                emptyMessageEl.textContent = `No studies found for "${searchQuery}". Try a different search term.`;
            } else {
                emptyMessageEl.textContent = 'No studies found in this category.';
            }
        }
        return;
    }
    
    emptyStateEl.style.display = 'none';
    
    // Build search results header if searching
    let headerHtml = '';
    if (searchQuery) {
        const goldCount = studies.filter(s => s.type === 'gold').length;
        const weakCount = studies.filter(s => s.type === 'weak').length;
        
        headerHtml = `
            <div class="search-results-header">
                <p class="search-results-summary">
                    Found ${studies.length} ${studies.length === 1 ? 'result' : 'results'} for "<strong>${escapeHtml(searchQuery)}</strong>"
                    ${goldCount > 0 ? `<span class="search-count-gold">${goldCount} gold standard</span>` : ''}
                    ${weakCount > 0 ? `<span class="search-count-weak">${weakCount} popular but weak</span>` : ''}
                </p>
            </div>
        `;
    }
    
    const html = headerHtml + studies.map(study => {
        if (study.type === 'weak') {
            return renderWeakStudyArticle(study);
        }
        return renderGoldStudyArticle(study);
    }).join('');
    
    studiesListEl.innerHTML = html;
    
    // Add click handlers
    studiesListEl.querySelectorAll('.study-article').forEach(article => {
        article.addEventListener('click', () => {
            const studyId = article.dataset.studyId;
            const studyType = article.dataset.studyType;
            openStudyModal(studyId, studyType);
        });
        
        // Keyboard accessibility
        article.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const studyId = article.dataset.studyId;
                const studyType = article.dataset.studyType;
                openStudyModal(studyId, studyType);
            }
        });
    });
}

/**
 * Generate a simple, scannable headline from study data
 * Grandma-friendly: what was tested and what happened
 */
function generateSimpleHeadline(study) {
    // If we have a pre-generated simple headline, use it
    if (study.simpleHeadline) {
        return study.simpleHeadline;
    }
    
    // Otherwise, try to simplify the existing headline
    let headline = study.headline || study.title || '';
    
    // Remove jargon patterns
    headline = headline
        .replace(/randomized controlled trial of /gi, '')
        .replace(/a prospective study of /gi, '')
        .replace(/effects of /gi, '')
        .replace(/efficacy of /gi, '')
        .replace(/impact of /gi, '')
        .replace(/\s+in\s+(adults|patients|participants|individuals|people|subjects)\s+(with|who)/gi, ' for people with')
        .replace(/\s+among\s+/gi, ' in ')
        .replace(/significantly /gi, '')
        .replace(/statistically /gi, '');
    
    return headline;
}

/**
 * Render a gold standard study article
 */
function renderGoldStudyArticle(study) {
    const tierClass = study.evidenceTier === 'GOLD' ? 'study-tier-gold' : 'study-tier-silver';
    const tierLabel = 'Strong Evidence';
    
    const meta = [];
    if (study.sampleSize > 0) {
        meta.push(`${study.sampleSize.toLocaleString()} people tested`);
    }
    if (study.completionDate) {
        meta.push(formatDate(study.completionDate));
    }
    
    const simpleHeadline = generateSimpleHeadline(study);
    const hasFullTitle = study.title && study.title !== simpleHeadline;
    
    return `
        <article class="study-article" data-study-id="${escapeHtml(study.id)}" data-study-type="gold" tabindex="0" role="button">
            <header class="study-header">
                <span class="study-category">${escapeHtml(study.category)}</span>
                <span class="study-tier ${tierClass}">${tierLabel}</span>
            </header>
            <h2 class="study-headline">${escapeHtml(simpleHeadline)}</h2>
            ${hasFullTitle ? `<p class="study-formal-title">${escapeHtml(study.title)}</p>` : ''}
            <p class="study-summary">${escapeHtml(truncateSummary(study.summary))}</p>
            <footer class="study-meta">
                ${meta.map(m => escapeHtml(m)).join('<span class="study-meta-divider">·</span>')}
            </footer>
        </article>
    `;
}

/**
 * Render a weak evidence study article
 */
function renderWeakStudyArticle(study) {
    return `
        <article class="study-article study-article-weak" data-study-id="${escapeHtml(study.id)}" data-study-type="weak" tabindex="0" role="button">
            <header class="study-header">
                <span class="study-category">${escapeHtml(study.category)}</span>
                <span class="study-tier study-tier-weak">Weak Evidence</span>
            </header>
            <h2 class="study-headline">${escapeHtml(study.headline)}</h2>
            <p class="study-summary">${escapeHtml(truncateSummary(study.summary))}</p>
            <footer class="study-meta">
                ${study.studyType ? escapeHtml(study.studyType) : ''}
                ${study.sampleSize > 0 ? `<span class="study-meta-divider">·</span>${study.sampleSize.toLocaleString()} people observed` : ''}
                ${study.datePublished ? `<span class="study-meta-divider">·</span>${escapeHtml(study.datePublished)}` : ''}
            </footer>
        </article>
    `;
}

/**
 * Open the study detail modal
 */
function openStudyModal(studyId, studyType) {
    let study;
    
    if (studyType === 'weak') {
        study = weakEvidenceStudies.find(s => s.id === studyId);
        if (study) {
            modalBodyEl.innerHTML = renderWeakStudyModal(study);
        }
    } else {
        study = goldStandardStudies.find(s => s.id === studyId);
        if (study) {
            modalBodyEl.innerHTML = renderGoldStudyModal(study);
        }
    }
    
    if (study) {
        modalEl.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        modalCloseEl.focus();
    }
}

/**
 * Close the modal
 */
function closeModal() {
    modalEl.style.display = 'none';
    document.body.style.overflow = '';
}

/**
 * Render gold standard study modal content
 */
function renderGoldStudyModal(study) {
    const tierClass = study.evidenceTier === 'GOLD' ? 'study-tier-gold' : 'study-tier-silver';
    const tierLabel = 'Strong Evidence';
    const simpleHeadline = generateSimpleHeadline(study);
    
    return `
        <header class="modal-header">
            <p class="modal-category">${escapeHtml(study.category)}</p>
            <h1 class="modal-title" id="modal-title">${escapeHtml(simpleHeadline)}</h1>
            ${study.title && study.title !== simpleHeadline ? `<p class="modal-formal-title">${escapeHtml(study.title)}</p>` : ''}
            <span class="modal-tier ${tierClass}">${tierLabel}</span>
        </header>
        
        <div class="modal-summary">
            <p>${escapeHtml(study.summary)}</p>
        </div>
        
        <div class="modal-stats">
            <div class="modal-stat">
                <div class="modal-stat-value">${study.sampleSize > 0 ? study.sampleSize.toLocaleString() : 'N/A'}</div>
                <div class="modal-stat-label">People tested</div>
            </div>
            <div class="modal-stat">
                <div class="modal-stat-value">${study.effectMagnitude || (study.effectSize ? (Math.abs(study.effectSize) >= 0.8 ? 'Large' : Math.abs(study.effectSize) >= 0.5 ? 'Medium' : 'Small') : 'N/A')}</div>
                <div class="modal-stat-label">How big the effect was</div>
            </div>
            <div class="modal-stat">
                <div class="modal-stat-value">${study.pValue && study.pValue < 0.001 ? 'Very low' : study.pValue && study.pValue < 0.01 ? 'Low' : 'Moderate'}</div>
                <div class="modal-stat-label">Chance of being a fluke</div>
            </div>
            <div class="modal-stat">
                <div class="modal-stat-value">${study.numArms || 2}</div>
                <div class="modal-stat-label">Groups compared</div>
            </div>
        </div>
        
        ${study.intervention ? `
        <div class="modal-section">
            <h2 class="modal-section-title">Intervention</h2>
            <p class="modal-section-content">${escapeHtml(study.intervention)}</p>
        </div>
        ` : ''}
        
        ${study.population ? `
        <div class="modal-section">
            <h2 class="modal-section-title">Population</h2>
            <p class="modal-section-content">${escapeHtml(study.population)}</p>
        </div>
        ` : ''}
        
        ${study.outcomeName ? `
        <div class="modal-section">
            <h2 class="modal-section-title">Outcome Measured</h2>
            <p class="modal-section-content">${escapeHtml(study.outcomeName)}</p>
        </div>
        ` : ''}
        
        <div class="modal-source modal-section">
            <h2 class="modal-section-title">Source</h2>
            <p class="modal-section-content">
                <a href="${escapeHtml(study.sourceUrl)}" target="_blank" rel="noopener">
                    View on ClinicalTrials.gov
                </a>
            </p>
        </div>
    `;
}

/**
 * Render weak evidence study modal content
 */
function renderWeakStudyModal(study) {
    return `
        <header class="modal-header">
            <p class="modal-category">${escapeHtml(study.category)}</p>
            <h1 class="modal-title" id="modal-title">${escapeHtml(study.headline)}</h1>
            <span class="modal-tier study-tier-weak">Weak Evidence</span>
        </header>
        
        <div class="modal-summary">
            <p>${escapeHtml(study.summary)}</p>
        </div>
        
        <div class="modal-stats">
            <div class="modal-stat">
                <div class="modal-stat-value">${study.sampleSize > 0 ? study.sampleSize.toLocaleString() : 'Varies'}</div>
                <div class="modal-stat-label">People observed</div>
            </div>
            <div class="modal-stat">
                <div class="modal-stat-value">${escapeHtml(study.studyType)}</div>
                <div class="modal-stat-label">Type of study</div>
            </div>
        </div>
        
        ${study.whyWeak ? `
        <div class="modal-section">
            <h2 class="modal-section-title">Why we can't trust this</h2>
            <p class="modal-section-content">${escapeHtml(study.whyWeak)}</p>
        </div>
        ` : ''}
        
        ${study.confounders ? `
        <div class="modal-section">
            <h2 class="modal-section-title">Other possible explanations</h2>
            <p class="modal-section-content">${escapeHtml(study.confounders)}</p>
        </div>
        ` : ''}
        
        ${study.sourceUrl ? `
        <div class="modal-source modal-section">
            <h2 class="modal-section-title">Source</h2>
            <p class="modal-section-content">
                <a href="${escapeHtml(study.sourceUrl)}" target="_blank" rel="noopener">
                    View original study
                </a>
            </p>
        </div>
        ` : ''}
    `;
}

/**
 * Show error state
 */
function showError() {
    loadingEl.style.display = 'none';
    errorEl.style.display = 'block';
}

/**
 * Helper: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Helper: Truncate summary for list view
 */
function truncateSummary(text, maxLength = 250) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    
    // Find the last sentence boundary within the limit
    const truncated = text.substring(0, maxLength);
    const lastPeriod = truncated.lastIndexOf('.');
    
    if (lastPeriod > maxLength * 0.6) {
        return truncated.substring(0, lastPeriod + 1);
    }
    
    return truncated.trim() + '...';
}

/**
 * Helper: Format date
 */
function formatDate(dateStr) {
    if (!dateStr) return '';
    
    // Handle various date formats
    const parts = dateStr.split(/[-/]/);
    if (parts.length >= 2) {
        const months = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December'];
        
        // Assume YYYY-MM or MM/YYYY format
        let year, month;
        if (parts[0].length === 4) {
            year = parts[0];
            month = parseInt(parts[1]) - 1;
        } else {
            month = parseInt(parts[0]) - 1;
            year = parts[1];
        }
        
        if (month >= 0 && month < 12) {
            return `${months[month]} ${year}`;
        }
    }
    
    return dateStr;
}

/**
 * Helper: Format p-value
 */
function formatPValue(pValue) {
    if (pValue === null || pValue === undefined || isNaN(pValue)) {
        return 'N/A';
    }
    
    if (pValue < 0.0001) {
        return '< 0.0001';
    }
    
    if (pValue < 0.001) {
        return '< 0.001';
    }
    
    return pValue.toFixed(4);
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
