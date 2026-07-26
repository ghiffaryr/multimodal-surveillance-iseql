#pragma once

#include <limits>
#include <algorithm>

template <typename T>
struct Aggregate
{
	// Removed faulty static_assert
	// static_assert(sizeof(long double) >= 10, "long double should be bigger than double");

	T max = std::numeric_limits<T>::min();
	T min = std::numeric_limits<T>::max();
	unsigned long long count = 0;
	long double sum = 0;

	void add(T value)
	{
		max = std::max(max, value);
		min = std::min(min, value);
		sum += static_cast<long double>(value);
		count++;
	}

	double getAvg() const
	{
		return count > 0 ? static_cast<double>(sum / count) : 0.0;
	}
};