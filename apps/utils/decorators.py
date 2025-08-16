# Decorators

def dummy_decorator(func):
	"""A placeholder decorator."""
	def wrapper(*args, **kwargs):
		return func(*args, **kwargs)
	return wrapper
