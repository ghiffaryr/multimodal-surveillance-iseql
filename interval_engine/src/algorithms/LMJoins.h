#pragma once

#include "LMJoin0.h"



//#define leungMuntzJoin leungMuntzJoin2
//#define leungMuntzJoin leungMuntzJoin4
#define leungMuntzJoin leungMuntzJoin5
//#define leungMuntzJoin leungMuntzJoin3


#ifdef COUNTERS
static unsigned long long lmComparisonCount = 0;
#endif


inline void sortRelationByEnd(Relation& relation)
{
	std::sort(relation.begin(), relation.end(), [] (const Tuple& lhs, const Tuple& rhs)
	{
		return lhs.end < rhs.end;
	});
}


template <typename Consumer>
void leungMuntzBeforeJoin(const Relation& X, const Relation& Y, Timestamp delta, Consumer&& consumer) noexcept
{
	leungMuntzJoin(X, Y,
		[] (const Tuple&        , const Tuple&        ) { return false;                         },
		[] (const Tuple& bufferX, const Tuple& bufferY) { return bufferY.start < bufferX.end;   },
		[delta] (const Tuple& x, const Tuple& y, Timestamp tau)
		{
			#ifdef COUNTERS
			lmComparisonCount++;
			#endif

			auto startY = y.start + tau;

			return x.end + delta + 1 < startY;
		},
		[] (const Tuple& y, const Tuple& x, Timestamp tau)
		{
			#ifdef COUNTERS
			lmComparisonCount++;
			#endif

			auto startX = x.end + tau;

			return y.start < startX;
		},
		[&consumer, delta] (const Tuple& x, const Tuple& y)
		{
			#ifdef COUNTERS
			lmCounterBeforeSelection++;
			#endif

			if (x.end <= y.start && y.start - x.end <= delta)
			{
				#ifdef COUNTERS
				lmCounterAfterSelection++;
				#endif

				consumer(x, y);
			}
		}
	);
}

template <typename Consumer>
void leungMuntzStartPrecedingBaseJoin(const Relation& X, const Relation& Y, Consumer&& consumer) noexcept
{
	leungMuntzJoin(X, Y,
		[] (const Tuple&        , const Tuple&        ) { return false;                         },
		[] (const Tuple& bufferX, const Tuple& bufferY) { return bufferY.start < bufferX.start; },
		[] (const Tuple& x, const Tuple& y, Timestamp tau)
		{
			#ifdef COUNTERS
			lmComparisonCount++;
			#endif

			auto startY = y.start + tau;

			return x.end   < startY;
		},
		[] (const Tuple& y, const Tuple& x, Timestamp tau)
		{
			#ifdef COUNTERS
			lmComparisonCount++;
			#endif

			auto startX = x.start + tau;

			return y.start < startX;
		},
		consumer
	);
}


template <typename Consumer>
void leungMuntzReverseDuringStrictJoin(const Relation& X, const Relation& Y, Consumer&& consumer) noexcept
{
	leungMuntzStartPrecedingBaseJoin(
		X,
		Y,
		[&consumer] (const Tuple& x, const Tuple& y)
		{
			#ifdef COUNTERS
			lmCounterBeforeSelection++;
			#endif

			if (x.start < y.start && y.end < x.end)
			{
				#ifdef COUNTERS
				lmCounterAfterSelection++;
				#endif

				consumer(x, y);
			}
		}
	);
}



template <typename Consumer>
void leungMuntzStartPrecedingStrictJoin(const Relation& X, const Relation& Y, Consumer&& consumer) noexcept
{
	leungMuntzStartPrecedingBaseJoin(
		X,
		Y,
		[&consumer] (const Tuple& x, const Tuple& y)
		{
			#ifdef COUNTERS
			lmCounterBeforeSelection++;
			#endif

			if (x.start < y.start && y.start < x.end)
			{
				#ifdef COUNTERS
				lmCounterAfterSelection++;
				#endif

				consumer(x, y);
			}
		}
	);
}






template <typename Consumer>
void leungMuntzLeftOverlapStrictJoin(const Relation& X, const Relation& Y, Consumer&& consumer) noexcept
{
	leungMuntzStartPrecedingBaseJoin(
		X,
		Y,
		[&consumer] (const Tuple& x, const Tuple& y)
		{
			#ifdef COUNTERS
			lmCounterBeforeSelection++;
			#endif

			if (x.start < y.start && y.start < x.end && x.end < y.end)
			{
				#ifdef COUNTERS
				lmCounterAfterSelection++;
				#endif

				consumer(x, y);
			}
		}
	);
}



