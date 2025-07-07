"""
LLM-based Property Scoring Module using Google Gemini API.
"""
import os
import re
import json
from typing import Dict, Optional, Tuple
from google import genai

class PropertyScorer:
    """Class for scoring properties using LLM analysis with continuous scoring."""
    
    def __init__(self, api_key: str):
        """Initialize the property scorer with Gemini API key."""
        self.client = genai.Client(api_key=api_key)
        
    def analyze_property(self, property_details: Dict) -> Dict:
        """
        Analyze a property using LLM and return enriched data with scoring.
        
        Args:
            property_details: Dictionary containing property information
            
        Returns:
            Dictionary with original data plus LLM analysis and scoring
        """
        # Extract basic info (handle None values)
        description = property_details.get('description', '') or ''
        price_text = property_details.get('price', '') or ''
        surface_text = property_details.get('surface', '') or ''
        neighbourhood = property_details.get('neighbourhood', '') or ''
        
        # Create analysis prompt
        prompt = f"""
Analyze this property listing and answer these specific questions:

Property Details:
- Price: {price_text}
- Surface: {surface_text}  
- Neighbourhood: {neighbourhood}
- Description: {description}

Questions (answer each on a new line with just the answer):
1. What neighborhood/barrio is this in? (e.g., "Belgrano", "Florida", "Palermo", "Vicente López" - NOT street names or "Planta Baja")
2. Is this on ground floor? (yes/no - look for "planta baja", "PB", "ground floor")
3. Does it have outdoor space? (yes/no - look for "terraza", "patio", "jardín", "balcón")
4. What type of outdoor space? (if any: "terraza", "patio", "jardín", "balcón", or "none")
5. Is it near important avenues? (yes/no - look for "av maipu", "av libertador", "av cabildo", "av santa fe", "panamericana")
6. Is it near subway/train? (yes/no - look for "subte", "tren", "estación", "metro", "línea")
"""
        
        try:
            # Call Gemini API for analysis
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',  # Using flash model to avoid rate limits
                contents=prompt
            )
            
            # Parse response
            if response.text:
                lines = response.text.strip().split('\n')
            else:
                print(f"LLM returned no text for property {property_details.get('url', 'N/A')}. Setting default analysis.")
                lines = ['N/A', 'no', 'no', 'none', 'no', 'no'] # Provide default values for all expected lines

            analysis = {
                'neighbourhood': lines[0].strip() if len(lines) > 0 else '',
                'is_ground_floor': 'yes' in lines[1].lower() if len(lines) > 1 else False,
                'has_outdoor_space': 'yes' in lines[2].lower() if len(lines) > 2 else False,
                'outdoor_space_type': lines[3].strip() if len(lines) > 3 else 'none',
                'near_important_avenue': 'yes' in lines[4].lower() if len(lines) > 4 else False,
                'near_subway_train': 'yes' in lines[5].lower() if len(lines) > 5 else False,
                'description_original': description
            }
            
            # Extract numeric values using regex (handle None values)
            price_match = None
            if price_text and isinstance(price_text, str):
                price_match = re.search(r'[\d.,]+', price_text.replace('$', '').replace('.', ''))
            analysis['price_numeric'] = int(price_match.group().replace(',', '')) if price_match else 0
            
            surface_match = None
            if surface_text and isinstance(surface_text, str):
                surface_match = re.search(r'(\d+)', surface_text)
            analysis['surface_m2'] = int(surface_match.group(1)) if surface_match else 0
            
            # Calculate score
            score, score_breakdown = self._calculate_score(analysis)
            
            # Combine original data with LLM analysis and score
            result = property_details.copy()
            result.update({
                'llm_analysis': analysis,
                'score': score,
                'score_breakdown': score_breakdown
            })
            
            return result
            
        except Exception as e:
            print(f"Error analyzing property with LLM: {e}")
            # Return original data with error information
            result = property_details.copy()
            result.update({
                'llm_analysis': None,
                'score': 0,
                'score_breakdown': {'error': str(e)}
            })
            return result

    def _calculate_score(self, analysis: Dict) -> Tuple[int, Dict]:
        """Calculate property score with continuous scoring for surface and price."""
        score = 0
        score_breakdown = {}

        # Location-based scoring (categorical)
        location = analysis.get('neighbourhood', '').lower()
        if 'belgrano' in location:
            score += 15
            score_breakdown['Location (Belgrano)'] = 10
        elif 'florida' in location or 'vicente lópez' in location or 'vicente lopez' in location:
            score += 15
            score_breakdown['Location (Florida/V.Lopez)'] = 5

        # Ground floor bonus (categorical)
        if analysis.get('is_ground_floor'):
            score += 10
            score_breakdown['Ground Floor'] = 10

        # Outdoor space bonus (categorical)
        if analysis.get('has_outdoor_space'):
            score += 3
            score_breakdown['Outdoor Space'] = 3

        # Proximity bonuses (new)
        if analysis.get('near_important_avenue'):
            score += 5
            score_breakdown['Near Important Avenue'] = 5
            
        if analysis.get('near_subway_train'):
            score += 5
            score_breakdown['Near Subway/Train'] = 4

        # Deduction for commercial properties and storage spaces
        description = analysis.get('description_original', '').lower()
        if 'alquiler local' in description:
            score -= 15
            score_breakdown['Commercial Property (Alquiler Local)'] = -15
        elif 'local' in description:
            score -= 15
            score_breakdown['Commercial Property (Local)'] = -15
        elif 'deposito' in description:
            score -= 15
            score_breakdown['Commercial Property (Deposito)'] = -15

        # Deductions for unwanted property types (split)
        if 'eventos' in description:
            score -= 15
            score_breakdown['Unwanted Type (Event)'] = -10
        if 'habitación' in description:
            score -= 15
            score_breakdown['Unwanted Type (Room)'] = -10
        if 'alquiler diario' in description:
            score -= 15
            score_breakdown['Unwanted Type (Daily Rental)'] = -10

        # Surface area scoring (continuous - more surface = more points)
        surface = analysis.get('surface_m2', 0)
        if surface > 0:
            if surface >= 100:
                surface_points = 10
            elif surface >= 80:
                surface_points = 10
            elif surface >= 60:
                surface_points = 5
            elif surface >= 50:
                surface_points = -5
            elif surface >= 40:
                surface_points = -10
            else:
                surface_points = -15
            
            score += surface_points
            score_breakdown[f'Surface ({surface}m²)'] = surface_points

        # Price scoring (continuous - lower price = more points)
        price = analysis.get('price_numeric', 0)
        if price > 0:
            if price <= 400000:
                price_points = 15
            elif price <= 500000:
                price_points = 15
            elif price <= 600000:
                price_points = 12
            elif price <= 700000:
                price_points = 5
            elif price <= 800000:
                price_points = 3
            else:
                price_points = 0
            
            if price_points > 0:
                score += price_points
                score_breakdown[f'Price (${price:,})'] = price_points

        return score, score_breakdown


def get_scorer() -> Optional[PropertyScorer]:
    """Get a PropertyScorer instance if API key is available."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("⚠️  GEMINI_API_KEY not found in environment variables")
        return None
    
    try:
        return PropertyScorer(api_key)
    except Exception as e:
        print(f"⚠️  Failed to initialize PropertyScorer: {e}")
        return None 