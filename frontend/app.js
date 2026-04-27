
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

const META_ANALYSIS_PATTERN = /meta[-\s]?analysis|systematic review/i;
const RANDOMIZED_PATTERN = /randomi[sz]ed|randomized controlled trial|rct/i;

function detectMetaAnalysis(text) {
    return META_ANALYSIS_PATTERN.test(text || '');
}

function detectRandomized(text) {
    return RANDOMIZED_PATTERN.test(text || '');
}

/**
 * Determine verdict based on evidence tier and effect direction
 * Returns object with verdict text and confidence level
 */
function determineVerdict(study) {
    // For weak evidence studies
    if (study.type === 'weak' || study.evidenceTier === 'WEAK') {
        return {
            verdict: 'Probably not',
            confidence: 'Evidence is weak or flawed',
            className: 'verdict-weak'
        };
    }
    
    // For strong evidence, determine direction from effect or headline
    const hasPositiveEffect = study.effectSize > 0 || 
        (study.treatmentMean !== null && study.controlMean !== null && study.treatmentMean > study.controlMean);
    
    // Check headline for negative indicators
    const headline = (study.headline || study.title || '').toLowerCase();
    const isNegativeOutcome = headline.includes('no difference') || 
        headline.includes('no effect') || 
        headline.includes('similar') ||
        headline.includes('doesn\'t') ||
        headline.includes('does not');
    
    if (study.evidenceTier === 'GOLD') {
        if (isNegativeOutcome) {
            return {
                verdict: 'No',
                confidence: 'Strong evidence shows no effect',
                className: 'verdict-no'
            };
        }
        return {
            verdict: 'Yes',
            confidence: 'Strong evidence supports this',
            className: 'verdict-yes'
        };
    }
    
    if (study.evidenceTier === 'SILVER') {
        if (isNegativeOutcome) {
            return {
                verdict: 'Probably not',
                confidence: 'Good evidence suggests no effect',
                className: 'verdict-probably-not'
            };
        }
        return {
            verdict: 'Likely yes',
            confidence: 'Good evidence supports this',
            className: 'verdict-likely'
        };
    }
    
    // Bronze or unknown
    return {
        verdict: 'Uncertain',
        confidence: 'More research needed',
        className: 'verdict-uncertain'
    };
}

/**
 * Initialize the application
 */
async function init() {
    try {
        // Load both data sources in parallel
        const [goldData, weakData] = await Promise.all([
            loadCSV('data/clinical_trials.csv'),
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
 * Process gold standard trial data: one study per nct_id, with all outcomes aggregated
 */
function processGoldStandardData(data) {
    const rows = data.filter(row => (row.study_id || row.nct_id) && row.headline);
    const byStudy = {};
    const tierRank = { GOLD: 3, SILVER: 2, BRONZE: 1 };
    rows.forEach(row => {
        const studyId = row.study_id || row.nct_id;
        const metaSource = `${row.title || ''} ${row.headline || ''} ${row.summary || ''}`;
        const isMetaAnalysis = detectMetaAnalysis(metaSource);
        const isRandomized = !isMetaAnalysis;
        const outcome = {
            headline: row.headline || '',
            summary: row.summary || '',
            outcomeName: row.outcome_name || '',
            outcomeType: row.outcome_type || '',
            controlMean: parseFloat(row.control_mean) || null,
            treatmentMean: parseFloat(row.treatment_mean) || null,
            effectSize: parseFloat(row.effect_size) || null,
            effectMagnitude: row.effect_magnitude || '',
            pValue: parseFloat(row.p_value) || null,
            ultraScore: parseFloat(row.ultra_score) || 0,
            analysisParamType: row.analysis_param_type || '',
            analysisParamValue: row.analysis_param_value || ''
        };
        if (!byStudy[studyId]) {
            byStudy[studyId] = {
                id: studyId,
                type: 'gold',
                category: (row.category || 'health').toLowerCase(),
                evidenceTier: row.evidence_tier || 'GOLD',
                title: row.title || '',
                intervention: row.intervention || '',
                interventionDescription: row.intervention_description || '',
                comparator: row.comparator || '',
                population: row.population || '',
                conditions: row.conditions || '',
                sampleSize: parseInt(row.sample_size) || 0,
                studyEnrollment: parseInt(row.study_enrollment) || parseInt(row.sample_size) || 0,
                sampleSizeCategory: row.sample_size_category || '',
                numArms: parseInt(row.num_arms) || 2,
                datePublished: row.date_published || row.completion_date || '',
                sourceUrl: row.source_url || (studyId.startsWith('NCT') ? `https://clinicaltrials.gov/study/${studyId}` : ''),
                isRandomized,
                isMetaAnalysis,
                outcomes: []
            };
        }
        byStudy[studyId].sampleSize = Math.max(byStudy[studyId].sampleSize, parseInt(row.sample_size) || 0);
        byStudy[studyId].outcomes.push(outcome);
        const r = tierRank[row.evidence_tier] || 0;
        if (r > (tierRank[byStudy[studyId].evidenceTier] || 0)) byStudy[studyId].evidenceTier = row.evidence_tier;
    });
    return Object.values(byStudy).map(study => {
        study.outcomes.sort((a, b) => b.ultraScore - a.ultraScore);
        const primary = study.outcomes[0];
        study.headline = primary.headline;
        study.summary = primary.summary;
        study.outcomeName = primary.outcomeName;
        study.outcomeType = primary.outcomeType;
        study.controlMean = primary.controlMean;
        study.treatmentMean = primary.treatmentMean;
        study.effectSize = primary.effectSize;
        study.effectMagnitude = primary.effectMagnitude;
        study.pValue = primary.pValue;
        study.ultraScore = primary.ultraScore;
        if (study.sampleSize === 0) study.sampleSize = study.studyEnrollment;
        return study;
    }).sort((a, b) => b.ultraScore - a.ultraScore);
}

/**
 * Process weak evidence data
 */
function processWeakEvidenceData(data) {
    return data
        .filter(row => row.claim || row.headline)
        .map(row => {
            const metaSource = `${row.study_type || ''} ${row.headline || ''} ${row.summary || ''}`;
            const isMetaAnalysis = detectMetaAnalysis(metaSource);
            const isRandomized = !isMetaAnalysis && detectRandomized(metaSource);

            return ({
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
                datePublished: row.date_published || '',
                isRandomized,
                isMetaAnalysis
            });
        });
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
 * Convert a statement headline into a question
 * "Eating more fiber lowers blood pressure" -> "Does eating more fiber lower blood pressure?"
 */
function convertToQuestion(headline) {
    if (!headline) return headline;
    
    // Already a question
    if (headline.trim().endsWith('?')) {
        return headline;
    }
    
    const lowerHeadline = headline.toLowerCase();
    
    // Pattern: "X reduces/lowers/improves/helps/increases Y"
    // Convert to "Does X reduce/lower/improve/help/increase Y?"
    const actionPatterns = [
        { regex: /^(.+?)\s+(reduces?)\s+(.+)$/i, verb: 'reduce' },
        { regex: /^(.+?)\s+(lowers?)\s+(.+)$/i, verb: 'lower' },
        { regex: /^(.+?)\s+(improves?)\s+(.+)$/i, verb: 'improve' },
        { regex: /^(.+?)\s+(helps?)\s+(.+)$/i, verb: 'help' },
        { regex: /^(.+?)\s+(increases?)\s+(.+)$/i, verb: 'increase' },
        { regex: /^(.+?)\s+(prevents?)\s+(.+)$/i, verb: 'prevent' },
        { regex: /^(.+?)\s+(causes?)\s+(.+)$/i, verb: 'cause' },
        { regex: /^(.+?)\s+(boosts?)\s+(.+)$/i, verb: 'boost' },
        { regex: /^(.+?)\s+(affects?)\s+(.+)$/i, verb: 'affect' },
        { regex: /^(.+?)\s+(protects?)\s+(.+)$/i, verb: 'protect' },
    ];
    
    for (const { regex, verb } of actionPatterns) {
        const match = headline.match(regex);
        if (match) {
            const subject = match[1].trim();
            const object = match[3].trim();
            // Capitalize first letter of subject
            const capitalSubject = subject.charAt(0).toLowerCase() + subject.slice(1);
            return `Does ${capitalSubject} ${verb} ${object}?`;
        }
    }
    
    // Pattern: "X is/are good/bad for Y"
    const qualityMatch = headline.match(/^(.+?)\s+(is|are)\s+(good|bad|better|worse|healthy|unhealthy|beneficial|harmful)\s+(for\s+.+)$/i);
    if (qualityMatch) {
        const subject = qualityMatch[1].trim();
        const verb = qualityMatch[2].toLowerCase();
        const quality = qualityMatch[3].toLowerCase();
        const rest = qualityMatch[4].trim();
        const capitalSubject = subject.charAt(0).toLowerCase() + subject.slice(1);
        return `${verb === 'is' ? 'Is' : 'Are'} ${capitalSubject} ${quality} ${rest}?`;
    }
    
    // Pattern: "X works/helps for Y" -> "Does X work/help for Y?"
    const worksMatch = headline.match(/^(.+?)\s+(works?|helps?)\s+(for|with|against)\s+(.+)$/i);
    if (worksMatch) {
        const subject = worksMatch[1].trim();
        const verb = worksMatch[2].toLowerCase().replace(/s$/, '');
        const prep = worksMatch[3].toLowerCase();
        const object = worksMatch[4].trim();
        const capitalSubject = subject.charAt(0).toLowerCase() + subject.slice(1);
        return `Does ${capitalSubject} ${verb} ${prep} ${object}?`;
    }
    
    // Pattern: Starting with verb (imperative) - "Get more sleep..." -> "Should you get more sleep...?"
    const imperativeMatch = headline.match(/^(get|eat|drink|take|try|do|exercise|walk|run|sleep|avoid)\s+(.+)$/i);
    if (imperativeMatch) {
        const verb = imperativeMatch[1].toLowerCase();
        const rest = imperativeMatch[2].trim();
        return `Should you ${verb} ${rest}?`;
    }
    
    // Fallback: prepend "Does" or check if it's about a claim
    // If headline contains "may", "might", "could" - ask if it's true
    if (/\b(may|might|could|can)\b/i.test(headline)) {
        return `Is it true that ${headline.charAt(0).toLowerCase()}${headline.slice(1)}?`;
    }
    
    // Last resort: Just add "Does" at the start if it seems like a statement about effects
    if (/\b(effect|impact|benefit|risk|outcome)\b/i.test(lowerHeadline)) {
        return headline + '?';
    }
    
    // Return as-is if we can't convert it
    return headline;
}

/**
 * Generate a simple, scannable headline from study data
 * Grandma-friendly: what was tested and what happened
 */
function generateSimpleHeadline(study) {
    // If we have a pre-generated simple headline, use it
    if (study.simpleHeadline) {
        return convertToQuestion(study.simpleHeadline);
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
    
    // Convert to question format
    return convertToQuestion(headline);
}

/**
 * Render method tags (RCT, meta-analysis)
 */
function renderMethodTags(study, classPrefix = 'study') {
    const tags = [];

    if (study.isRandomized) {
        // Use a gold medal SVG to make randomized trials more prominent while keeping accessible text
        tags.push({
            label: `<img src="img/rct_gold_medal.svg" alt="Randomized trial" class="rct-medal" /><span class="${classPrefix}-method-label">Randomized trial</span>`,
            className: `${classPrefix}-method ${classPrefix}-method-rct`
        });
    }

    if (study.isMetaAnalysis) {
        tags.push({
            label: 'Meta-analysis',
            className: `${classPrefix}-method ${classPrefix}-method-meta`
        });
    }

    if (tags.length === 0) {
        return '';
    }

    return tags.map(tag => `<span class="${tag.className}">${tag.label}</span>`).join('');
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
    // Add p-value to footer
    if (study.pValue !== null && study.pValue !== undefined && !isNaN(study.pValue)) {
        meta.push(`p ${formatPValue(study.pValue)}`);
    }
    // Add effect size to footer
    if (study.effectSize !== null && study.effectSize !== undefined && !isNaN(study.effectSize)) {
        const effectLabel = Math.abs(study.effectSize) >= 0.8 ? 'large effect' : 
                           Math.abs(study.effectSize) >= 0.5 ? 'medium effect' : 'small effect';
        meta.push(effectLabel);
    }
    if (study.datePublished) {
        meta.push(formatDate(study.datePublished));
    }
    
    const simpleHeadline = generateSimpleHeadline(study);
    const hasFullTitle = study.title && study.title !== simpleHeadline;
    const methodTags = renderMethodTags(study);
    const verdict = determineVerdict(study);
    const ateText = formatATE(study);
    const otherOutcomes = (study.outcomes && study.outcomes.length > 1) ? study.outcomes.slice(1) : [];
    const otherFindingsHtml = otherOutcomes.length ? `
            <div class="study-other-outcomes">
                <span class="study-other-outcomes-label">Also in this trial:</span>
                <ul class="study-other-outcomes-list">
                    ${otherOutcomes.map(o => `<li>${highlightText(truncateSummary(o.headline, 120), searchQuery)}</li>`).join('')}
                </ul>
            </div>
    ` : '';

    return `
        <article class="study-article" data-study-id="${escapeHtml(study.id)}" data-study-type="gold" tabindex="0" role="button">
            <header class="study-header">
                <span class="study-category">${escapeHtml(study.category)}</span>
                <div class="study-badges">
                    <span class="study-tier ${tierClass}">${tierLabel}</span>
                    ${methodTags}
                </div>
            </header>
            <h2 class="study-headline">${highlightText(simpleHeadline, searchQuery)}</h2>
            <div class="study-verdict ${verdict.className}">
                <span class="verdict-label">${verdict.verdict}</span>
                <span class="verdict-confidence">${verdict.confidence}</span>
            </div>
            ${hasFullTitle ? `<p class="study-formal-title">${highlightText(study.title, searchQuery)}</p>` : ''}
            <p class="study-summary">${highlightText(truncateSummary(study.summary), searchQuery)}</p>
            ${ateText ? `<p class="study-ate">${escapeHtml(ateText)}</p>` : ''}
            ${otherFindingsHtml}
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
    const methodTags = renderMethodTags(study);
    const verdict = determineVerdict(study);
    // Convert headline to question format if not already a question
    const questionHeadline = convertToQuestion(study.headline);
    return `
        <article class="study-article study-article-weak" data-study-id="${escapeHtml(study.id)}" data-study-type="weak" tabindex="0" role="button">
            <header class="study-header">
                <span class="study-category">${escapeHtml(study.category)}</span>
                <div class="study-badges">
                    <span class="study-tier study-tier-weak">Weak Evidence</span>
                    ${methodTags}
                </div>
            </header>
            <h2 class="study-headline">${highlightText(questionHeadline, searchQuery)}</h2>
            <div class="study-verdict ${verdict.className}">
                <span class="verdict-label">${verdict.verdict}</span>
                <span class="verdict-confidence">${verdict.confidence}</span>
            </div>
            <p class="study-summary">${highlightText(truncateSummary(study.summary), searchQuery)}</p>
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
 * Render gold standard study modal content (one trial, all outcomes in same style)
 */
function renderGoldStudyModal(study) {
    const tierClass = study.evidenceTier === 'GOLD' ? 'study-tier-gold' : 'study-tier-silver';
    const tierLabel = 'Strong Evidence';
    const simpleHeadline = generateSimpleHeadline(study);
    const methodTags = renderMethodTags(study, 'modal');
    const outcomes = study.outcomes && study.outcomes.length ? study.outcomes : [{ headline: study.headline, summary: study.summary, outcomeName: study.outcomeName, outcomeType: study.outcomeType, controlMean: study.controlMean, treatmentMean: study.treatmentMean, effectSize: study.effectSize, effectMagnitude: study.effectMagnitude, pValue: study.pValue, analysisParamType: study.analysisParamType, analysisParamValue: study.analysisParamValue }];

    function formatOutcomeStats(o) {
        const parts = [];
        if (o.pValue != null && !isNaN(o.pValue)) parts.push(`p ${o.pValue < 0.001 ? '<0.001' : o.pValue.toFixed(3)}`);
        if (o.analysisParamType && o.analysisParamValue) parts.push(`${o.analysisParamType}: ${o.analysisParamValue}`);
        if (o.effectMagnitude) parts.push(o.effectMagnitude + ' effect');
        if (o.effectSize != null && !isNaN(o.effectSize)) parts.push(`d = ${o.effectSize.toFixed(2)}`);
        return parts.length ? parts.join(' · ') : '';
    }

    const outcomesHtml = outcomes.map((o, i) => {
        const ateText = formatATE(o);
        return `
        <div class="modal-outcome">
            <h3 class="modal-outcome-headline">${highlightText(o.headline, searchQuery)}</h3>
            <p class="modal-outcome-summary">${highlightText(o.summary, searchQuery)}</p>
            ${o.outcomeName ? `<p class="modal-outcome-name">${escapeHtml(o.outcomeName)}</p>` : ''}
            ${ateText ? `<p class="modal-outcome-ate">${escapeHtml(ateText)}</p>` : ''}
            ${formatOutcomeStats(o) ? `<p class="modal-outcome-stats">${escapeHtml(formatOutcomeStats(o))}</p>` : ''}
        </div>
    `;
    }).join('');

    return `
        <header class="modal-header">
            <p class="modal-category">${escapeHtml(study.category)}</p>
            <h1 class="modal-title" id="modal-title">${highlightText(study.title || simpleHeadline, searchQuery)}</h1>
            <div class="modal-badges">
                <span class="modal-tier ${tierClass}">${tierLabel}</span>
                ${methodTags}
            </div>
        </header>
        
        <div class="modal-stats">
            <div class="modal-stat">
                <div class="modal-stat-value">${study.sampleSize > 0 ? study.sampleSize.toLocaleString() : 'N/A'}</div>
                <div class="modal-stat-label">People tested</div>
            </div>
            <div class="modal-stat">
                <div class="modal-stat-value">${study.numArms || 2}</div>
                <div class="modal-stat-label">Groups compared</div>
            </div>
        </div>
        
        ${study.intervention ? `
        <div class="modal-section">
            <h2 class="modal-section-title">Intervention</h2>
            <p class="modal-section-content">${highlightText(study.intervention, searchQuery)}</p>
        </div>
        ` : ''}
        
        ${study.population ? `
        <div class="modal-section">
            <h2 class="modal-section-title">Population</h2>
            <p class="modal-section-content">${highlightText(study.population, searchQuery)}</p>
        </div>
        ` : ''}
        
        <div class="modal-section">
            <h2 class="modal-section-title">${outcomes.length > 1 ? 'Findings' : 'Finding'}</h2>
            <div class="modal-outcomes">${outcomesHtml}</div>
        </div>
        
        <div class="modal-source modal-section">
            <h2 class="modal-section-title">Source</h2>
            <p class="modal-section-content">
                <a href="${escapeHtml(study.sourceUrl)}" target="_blank" rel="noopener">
                    ${study.sourceUrl && study.sourceUrl.includes('pubmed') ? 'View on PubMed' : 'View on ClinicalTrials.gov'}
                </a>
            </p>
        </div>
    `;
}

/**
 * Render weak evidence study modal content
 */
function renderWeakStudyModal(study) {
    const methodTags = renderMethodTags(study, 'modal');
    return `
        <header class="modal-header">
            <p class="modal-category">${escapeHtml(study.category)}</p>
            <h1 class="modal-title" id="modal-title">${highlightText(study.headline, searchQuery)}</h1>
            <div class="modal-badges">
                <span class="modal-tier study-tier-weak">Weak Evidence</span>
                ${methodTags}
            </div>
        </header>
        
        <div class="modal-summary">
            <p>${highlightText(study.summary, searchQuery)}</p>
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
            <p class="modal-section-content">${highlightText(study.whyWeak, searchQuery)}</p>
        </div>
        ` : ''}
        
        ${study.confounders ? `
        <div class="modal-section">
            <h2 class="modal-section-title">Other possible explanations</h2>
            <p class="modal-section-content">${highlightText(study.confounders, searchQuery)}</p>
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
 * Helper: Escape regex characters
 */
function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Helper: Highlight matching search terms
 */
function highlightText(text, query) {
    if (!text) return '';
    if (!query) return escapeHtml(text);

    const terms = query.split(/\s+/).map(term => term.trim()).filter(Boolean);
    if (terms.length === 0) {
        return escapeHtml(text);
    }

    const uniqueTerms = Array.from(new Set(terms)).sort((a, b) => b.length - a.length);
    const pattern = uniqueTerms.map(escapeRegExp).join('|');
    const regex = new RegExp(pattern, 'gi');
    let result = '';
    let lastIndex = 0;
    let hasMatch = false;

    for (const match of text.matchAll(regex)) {
        hasMatch = true;
        const matchIndex = match.index ?? 0;
        result += escapeHtml(text.slice(lastIndex, matchIndex));
        result += `<mark class="search-highlight">${escapeHtml(match[0])}</mark>`;
        lastIndex = matchIndex + match[0].length;
    }

    if (!hasMatch) {
        return escapeHtml(text);
    }

    result += escapeHtml(text.slice(lastIndex));
    return result;
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

/**
 * Helper: Extract unit string from an outcome name, if present
 * Returns a lowercase short token (e.g. 'kg', 'lbs', '%', 'mmhg', 'bpm', 'mg/dL', 'cm', 'mL') or empty string
 */
function extractUnitFromOutcome(outcomeName) {
    if (!outcomeName) return '';

    // Look for a unit in parentheses: "Weight (kg)" or "Weight change (lbs)"
    const parenMatch = outcomeName.match(/\(([^)]+)\)/);
    if (parenMatch && parenMatch[1]) {
        const candidate = parenMatch[1].trim();
        const unitMatch = candidate.match(/kg|lb|lbs|%|mmhg|bpm|mg\/?dl|cm|mm|mL|ml/i);
        if (unitMatch) {
            const u = unitMatch[0].toLowerCase().replace(/ml/i, 'mL').replace(/mg\/dl/i, 'mg/dL');
            return u;
        }
        return candidate.toLowerCase();
    }

    // Look for units elsewhere in the string
    const elsewhere = outcomeName.match(/kg|lb|lbs|%|mmhg|bpm|mg\/?dl|cm|mm|mL|ml/i);
    if (elsewhere) return elsewhere[0].toLowerCase().replace(/ml/i, 'mL').replace(/mg\/dl/i, 'mg/dL');

    return '';
}

/**
 * Infer a likely unit from keywords when no explicit unit is present
 */
function inferUnitFromKeywords(outcomeName = '', outcomeType = '') {
    const lower = `${outcomeName} ${outcomeType}`.toLowerCase();

    if (/weight|weight change|weight loss|body weight|weight gain|kg body weight|lbs|pounds/.test(lower)) return 'lbs';
    if (/blood pressure|systolic|diastolic|mmhg/.test(lower)) return 'mmHg';
    if (/cholesterol|hdl|ldl|triglyceride|triglycerides|lipid/.test(lower)) return 'mg/dL';
    if (/glucose|blood sugar|glyco|hba1c/.test(lower)) return 'mg/dL';
    if (/heart rate|bpm|beats per minute/.test(lower)) return 'bpm';
    if (/percent|percentage|rate|percentage point|%/.test(lower)) return '%';
    if (/bmi/.test(lower)) return 'points';
    if (/height|waist|cm|inches|inch/.test(lower)) return 'in';
    if (/volume|ml|mL|milliliter/.test(lower)) return 'mL';

    return '';
}

/**
 * Convert a numeric value from a source unit into American-standard unit (lbs, in, etc.)
 * Returns { value: number, unit: string }
 */
function convertValueToAmerican(value, fromUnit) {
    if (fromUnit == null || fromUnit === '') return { value, unit: 'units' };
    const u = String(fromUnit).toLowerCase();

    if (u === 'kg') {
        return { value: value * 2.20462, unit: 'lbs' };
    }
    if (u === 'lb' || u === 'lbs' || u === 'pounds') {
        return { value: value, unit: 'lbs' };
    }
    if (u === 'cm') {
        return { value: value * 0.393701, unit: 'in' };
    }
    if (u === 'mm') {
        return { value: value * 0.0393701, unit: 'in' };
    }
    if (u === 'm' || u === 'meter' || u === 'metre') {
        return { value: value * 39.3701, unit: 'in' };
    }
    if (u === 'ml' || u === 'mL') {
        return { value: value, unit: 'mL' };
    }
    if (u === 'mg/dl' || u === 'mg/dl') {
        return { value: value, unit: 'mg/dL' };
    }
    if (u === 'mmhg') {
        return { value: value, unit: 'mmHg' };
    }
    if (u === '%' || u === 'percent' || u === 'percentage') {
        return { value: value, unit: '%' };
    }
    if (u === 'bpm') {
        return { value: value, unit: 'bpm' };
    }

    // Unknown -> return as-is but label 'units'
    return { value, unit: fromUnit };
}

/**
 * Helper: Format the ATE (average treatment effect) in plain English when possible
 * Returns an empty string when not applicable (missing means or not statistically significant)
 * Uses American units where possible and requires p < 0.001 to display
 */
function formatATE(study) {
    // Need both means and a p-value that indicates significance
    if (study.treatmentMean == null || study.controlMean == null || study.pValue == null) return '';
    if (isNaN(study.treatmentMean) || isNaN(study.controlMean) || isNaN(study.pValue)) return '';

    // Only show when statistically significant at the stricter threshold p < 0.001
    if (study.pValue >= 0.001) return '';

    const diff = study.treatmentMean - study.controlMean;
    const absDiff = Math.abs(diff);

    // Detect a unit (explicit or inferred). Prefer explicit units in outcomeName.
    let detectedUnit = extractUnitFromOutcome(study.outcomeName);
    if (!detectedUnit) {
        detectedUnit = inferUnitFromKeywords(study.outcomeName, study.outcomeType);
    }

    // If still not detected but outcomeType suggests percent
    if (!detectedUnit && study.outcomeType && /percent|percentages|proportion|percentile/i.test(study.outcomeType)) {
        detectedUnit = '%';
    }

    // Convert absolute difference to American unit where appropriate
    const converted = convertValueToAmerican(absDiff, detectedUnit);
    const rounded = Math.round(converted.value * 100) / 100; // two decimals

    // Determine phrasing depending on unit type
    const sign = diff < 0 ? 'lower' : 'higher';
    let sentence = '';

    if (converted.unit === 'lbs') {
        const verb = diff < 0 ? 'lost an average of' : 'gained an average of';
        sentence = `Treated participants ${verb} ${rounded} ${converted.unit} compared to the control group`;
    } else if (converted.unit === '%') {
        sentence = `Treated participants had an average ${rounded}% ${sign} compared to the control group`;
    } else if (converted.unit === 'units' || !converted.unit) {
        sentence = `Treated participants had an average difference of ${rounded} units compared to the control group`;
    } else if (converted.unit === 'points') {
        sentence = `Treated participants changed by an average of ${rounded} points compared to the control group`;
    } else {
        // general phrasing: 'were on average X UNIT lower/higher'
        sentence = `Treated participants were on average ${rounded} ${converted.unit} ${sign} than the control group`;
    }

    const pText = !isNaN(study.pValue) ? ` (p = ${formatPValue(study.pValue)})` : '';

    return sentence + pText + '.';
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
