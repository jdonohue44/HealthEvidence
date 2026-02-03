"""
Scoring functions for ultra-significant trial analysis.

This module provides functions to calculate effect sizes and score trials
based on statistical significance, effect magnitude, and sample size.
"""

import math


def cohens_d(mean_treatment, mean_control, sd_treatment, sd_control, n_treatment, n_control):
    """
    Calculate Cohen's d effect size with pooled standard deviation.
    
    Args:
        mean_treatment: Mean of treatment group
        mean_control: Mean of control group
        sd_treatment: Standard deviation of treatment group
        sd_control: Standard deviation of control group
        n_treatment: Sample size of treatment group
        n_control: Sample size of control group
        
    Returns:
        Cohen's d value, or None if calculation not possible
    """
    if None in (mean_treatment, mean_control, sd_treatment, sd_control, n_treatment, n_control):
        return None
    
    if n_treatment <= 1 or n_control <= 1:
        return None
    
    # Pooled standard deviation
    numerator = (n_treatment - 1) * sd_treatment**2 + (n_control - 1) * sd_control**2
    denominator = n_treatment + n_control - 2
    
    if denominator <= 0:
        return None
    
    pooled_sd = math.sqrt(numerator / denominator)
    
    if pooled_sd <= 0:
        return None
    
    return (mean_treatment - mean_control) / pooled_sd


def effect_magnitude(d):
    """
    Classify effect size magnitude based on Cohen's conventions.
    
    Args:
        d: Cohen's d value
        
    Returns:
        String classification: 'small', 'medium', 'large', or None
    """
    if d is None:
        return None
    
    abs_d = abs(d)
    
    if abs_d >= 0.8:
        return 'large'
    elif abs_d >= 0.5:
        return 'medium'
    elif abs_d >= 0.2:
        return 'small'
    else:
        return 'negligible'


def ultra_significance_score(p_value, effect_size, sample_size):
    """
    Calculate ultra-significance score for a trial outcome.
    
    The score combines:
    - Statistical significance (p-value must be < 0.001)
    - Effect size magnitude (must be >= 0.5)
    - Sample size (larger = more reliable)
    
    Args:
        p_value: The p-value (numeric, not string)
        effect_size: Cohen's d effect size
        sample_size: Total sample size
        
    Returns:
        Score value (0 if doesn't meet thresholds, positive otherwise)
    """
    # Must have valid p-value below threshold
    if p_value is None or p_value >= 0.001:
        return 0
    
    # Must have meaningful effect size
    if effect_size is None or abs(effect_size) < 0.5:
        return 0
    
    # Must have reasonable sample size
    if sample_size is None or sample_size < 20:
        return 0
    
    # Calculate component scores
    # p-value score: -log10(p) so smaller p = higher score
    p_score = -math.log10(max(p_value, 1e-20))
    
    # Effect size score: absolute value
    effect_score = abs(effect_size)
    
    # Sample size score: log scale so diminishing returns
    size_score = math.log10(max(sample_size, 10))
    
    return p_score * effect_score * size_score


def determine_evidence_tier(p_value, effect_size, sample_size=None, is_rct=True):
    """
    Determine evidence tier based on study characteristics.
    
    Gold Standard requires:
    - Randomized controlled trial design
    - p-value < 0.001 (very high statistical significance)
    - Effect size >= 0.5 (medium to large effect)
    - Sample size >= 100 (adequate power for reliable estimates)
    
    Args:
        p_value: The p-value (numeric)
        effect_size: Cohen's d effect size
        sample_size: Total number of participants enrolled
        is_rct: Whether this is a randomized controlled trial
        
    Returns:
        String tier: 'GOLD', 'SILVER', or 'BRONZE'
    """
    if not is_rct:
        return 'WEAK'
    
    if p_value is None or effect_size is None:
        return 'BRONZE'
    
    # Normalize sample size
    n = sample_size if sample_size is not None else 0
    
    # Gold: RCT with p < 0.001, large effect, AND adequate sample size
    # Minimum 100 participants for Gold (ensures reasonable statistical power)
    if p_value < 0.001 and abs(effect_size) >= 0.5 and n >= 100:
        return 'GOLD'
    
    # Silver: RCT with p < 0.01 and medium effect
    # Minimum 50 participants for Silver
    if p_value < 0.01 and abs(effect_size) >= 0.3 and n >= 50:
        return 'SILVER'
    
    return 'BRONZE'


def sample_size_descriptor(n):
    """
    Get a human-readable descriptor for sample size.
    
    Args:
        n: Number of participants
        
    Returns:
        String descriptor: 'small', 'moderate', 'large', 'very large'
    """
    if n is None or n < 50:
        return 'small'
    elif n < 200:
        return 'moderate'
    elif n < 1000:
        return 'large'
    else:
        return 'very large'
