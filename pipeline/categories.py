"""
Category assignment logic for clinical trials.

This module assigns trials to categories (nutrition, exercise, health)
based on intervention descriptions and condition keywords.
"""


NUTRITION_KEYWORDS = [
    'diet', 'dietary', 'nutrition', 'nutritional', 'food', 'eating',
    'calorie', 'caloric', 'protein', 'fiber', 'vitamin', 'mineral',
    'supplement', 'supplementation', 'meal', 'feeding', 'fasting',
    'carbohydrate', 'fat intake', 'sodium', 'salt', 'sugar',
    'mediterranean', 'dash diet', 'ketogenic', 'low-carb', 'plant-based',
    'vegan', 'vegetarian', 'whole grain', 'fruit', 'vegetable',
    'omega-3', 'fish oil', 'probiotic', 'prebiotic'
]

EXERCISE_KEYWORDS = [
    'exercise', 'physical activity', 'walking', 'training', 'workout',
    'fitness', 'aerobic', 'resistance', 'strength training', 'movement',
    'sport', 'running', 'jogging', 'cycling', 'swimming', 'yoga',
    'stretching', 'rehabilitation', 'mobility', 'endurance', 'hiit',
    'interval training', 'sedentary', 'step count', 'pedometer',
    'treadmill', 'weight training', 'muscle', 'cardio', 'cardiovascular exercise'
]


def assign_category(intervention_text, condition_text):
    """
    Assign a trial to a category based on intervention and condition keywords.
    
    Args:
        intervention_text: Description of the intervention
        condition_text: Description of conditions studied
        
    Returns:
        Category string: 'nutrition', 'exercise', or 'health'
    """
    if intervention_text is None:
        intervention_text = ''
    if condition_text is None:
        condition_text = ''
    
    text = f"{intervention_text} {condition_text}".lower()
    
    # Check nutrition keywords
    for keyword in NUTRITION_KEYWORDS:
        if keyword in text:
            return 'nutrition'
    
    # Check exercise keywords
    for keyword in EXERCISE_KEYWORDS:
        if keyword in text:
            return 'exercise'
    
    # Default to general health
    return 'health'


def get_category_display_name(category):
    """
    Get display-friendly category name.
    
    Args:
        category: Category string
        
    Returns:
        Display name with proper capitalization
    """
    names = {
        'nutrition': 'Nutrition',
        'exercise': 'Exercise',
        'health': 'Health'
    }
    return names.get(category, 'Health')
