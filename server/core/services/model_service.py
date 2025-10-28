"""
Model management service for handling AI model selection and configuration
"""

# Global variable to track current model (will be set by server.py)
current_model_id = None
models = {}


def set_models(models_dict: dict):
    """Set the available models dictionary"""
    global models
    models = models_dict


def set_current_model(model_id: str):
    """Set the current model ID"""
    global current_model_id
    current_model_id = model_id


def get_current_model_id() -> str:
    """Get the current model ID"""
    return current_model_id


def change_model(model_name: str) -> dict:
    """
    Change the current model

    Args:
        model_name: Name of the model to switch to

    Returns:
        Dictionary with success status and model info
    """
    global current_model_id

    if model_name not in models:
        return {
            "success": False,
            "error": f"Model '{model_name}' not found. Available models: {list(models.keys())}",
            "status_code": 400
        }

    # Update the current model
    current_model_id = models[model_name]

    print(f"Model changed to: {model_name} ({current_model_id})")

    return {
        "success": True,
        "message": f"Model changed to {model_name}",
        "model_name": model_name,
        "model_id": current_model_id
    }


def get_models_list() -> dict:
    """
    Get list of available models with their categories

    Returns:
        Dictionary with models list and count
    """
    model_list = []

    for model_name, model_id in models.items():
        # Determine model category based on model capabilities
        # Vision-capable models (available on-demand):
        # - Claude 3.5 and 3.x models (have vision)
        # Note: Only including models with on-demand throughput support
        model_name_lower = model_name.lower()

        if any(keyword in model_name_lower for keyword in [
            'claude',  # All Claude models have vision
        ]):
            category = "Text & Vision"
        else:
            category = "Text Only"

        model_list.append({
            "name": model_name,
            "id": model_id,
            "category": category
        })

    return {
        "models": model_list,
        "total_count": len(model_list)
    }


def get_current_model_info() -> dict:
    """
    Get the currently selected model information

    Returns:
        Dictionary with current model name and ID
    """
    # Find the model name for the current model ID
    current_model_name = None
    for name, model_id in models.items():
        if model_id == current_model_id:
            current_model_name = name
            break

    return {
        "current_model_name": current_model_name,
        "current_model_id": current_model_id
    }
