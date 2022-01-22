
# https://www.statology.org/normalize-data-between-0-and-100/

def normalize(value, min_value, max_value, min_normalized, max_normalized):
	if value < min_value or value > max_value:
		raise ValueError("Value out of range")
	return round(((value - min_value) / (max_value - min_value)) * (max_normalized - min_normalized) + min_normalized)


def denormalize(value_normalized, min_normalized, max_normalized, min_value, max_value):
	if value_normalized < min_normalized or value_normalized > max_normalized:
		raise ValueError("Value out of range")
	return round(((value_normalized - min_normalized) / (max_normalized - min_normalized)) * (max_value - min_value) + min_value)
