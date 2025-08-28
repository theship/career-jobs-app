"""
Utilities for handling pgvector data types and conversions
"""

import json
import logging
from typing import List, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)


def parse_pgvector_string(vector_str: Union[str, List, None]) -> Optional[np.ndarray]:
    """
    Parse pgvector string representation to numpy array
    
    PostgreSQL's vector type returns strings like: '[-0.016, 0.013, ...]'
    or sometimes: '["-0.016","0.013",...]'
    
    Args:
        vector_str: String representation of vector from pgvector
        
    Returns:
        Numpy array of floats, or None if parsing fails
    """
    if vector_str is None:
        return None
    
    # If already a list or array, convert to numpy
    if isinstance(vector_str, (list, np.ndarray)):
        try:
            return np.array(vector_str, dtype=np.float32)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert list to array: {e}")
            return None
    
    # Handle string representation
    if not isinstance(vector_str, str):
        logger.warning(f"Unexpected vector type: {type(vector_str)}")
        return None
    
    try:
        # Remove any numpy string wrapper if present
        if vector_str.startswith("np.str_('") and vector_str.endswith("')"):
            vector_str = vector_str[9:-2]
        
        # Clean the string
        vector_str = vector_str.strip()
        
        # Parse as JSON array
        if vector_str.startswith('[') and vector_str.endswith(']'):
            # Try direct JSON parsing
            try:
                vector_list = json.loads(vector_str)
                return np.array(vector_list, dtype=np.float32)
            except json.JSONDecodeError:
                # Fallback: manual parsing for PostgreSQL format
                # Remove brackets
                vector_str = vector_str[1:-1]
                # Split by comma and convert
                values = [float(x.strip()) for x in vector_str.split(',')]
                return np.array(values, dtype=np.float32)
        else:
            logger.warning(f"Vector string doesn't look like an array: {vector_str[:50]}...")
            return None
            
    except Exception as e:
        logger.error(f"Failed to parse vector string: {e}")
        logger.debug(f"Problematic vector string: {vector_str[:100]}...")
        return None


def ensure_vector_format(data: dict, vector_fields: List[str] = None) -> dict:
    """
    Ensure vector fields in a dictionary are properly formatted as numpy arrays
    
    Args:
        data: Dictionary potentially containing vector fields
        vector_fields: List of field names that should contain vectors
                      Defaults to ['embedding']
        
    Returns:
        Dictionary with vector fields converted to numpy arrays
    """
    if vector_fields is None:
        vector_fields = ['embedding']
    
    for field in vector_fields:
        if field in data and data[field] is not None:
            data[field] = parse_pgvector_string(data[field])
    
    return data


def batch_ensure_vectors(data_list: List[dict], vector_fields: List[str] = None) -> List[dict]:
    """
    Ensure vector fields for a list of dictionaries
    
    Args:
        data_list: List of dictionaries potentially containing vector fields
        vector_fields: List of field names that should contain vectors
        
    Returns:
        List with all vector fields properly converted
    """
    return [ensure_vector_format(item, vector_fields) for item in data_list]


def vectors_to_matrix(vectors: List[Optional[np.ndarray]]) -> Optional[np.ndarray]:
    """
    Convert list of vectors to a 2D numpy matrix for batch operations
    
    Args:
        vectors: List of numpy arrays (vectors)
        
    Returns:
        2D numpy array, or None if no valid vectors
    """
    valid_vectors = [v for v in vectors if v is not None]
    if not valid_vectors:
        return None
    
    try:
        return np.vstack(valid_vectors)
    except Exception as e:
        logger.error(f"Failed to stack vectors into matrix: {e}")
        return None