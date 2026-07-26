#pragma once

#include <set>

#include "Iterators.h"
#include "containers/GaplessHashMap.h"

template <typename Consumer>
void reverseDuringStrictJoinWithTree(const Relation& R, const Relation& S, const Consumer& consumer) noexcept
{
	struct Compare {
		bool operator()(const Tuple& left, const Tuple& right) {
			return std::tie(left.end, left.id) > std::tie(right.end, right.id);
		}
	};
	using Tree = std::set<Tuple, Compare>;

	Tree tree;

	Iterator itR(R.getIndex());
	FilteringIterator<Iterator> itS(Iterator(S.getIndex()), Endpoint::Type::START);
	std::less<Endpoint> comp;

	for (;;)
	{
		if (comp(itR.getEndpoint(), itS.getEndpoint()))
		{
			const Endpoint& endpointR = itR.getEndpoint();
			TID tid = endpointR.getTID();

			if (endpointR.isStart())
			{
				const auto& r = R[tid];
				assert(r.start == endpointR.getTimestamp());
				assert(r.id == static_cast<int>(tid));
				tree.insert(r);
			}
			else
			{
				Tuple r;
				r.end = endpointR.getTimestamp();
				r.id = static_cast<int>(tid);
				auto erased = tree.erase(r);
				assert(erased == 1); (void) erased;
			}

			itR.moveToNextEndpoint();
			if (itR.isFinished())
				break;
		}
		else
		{
			const Tuple& s = S[itS.getEndpoint().getTID()];

			for (const auto& r : tree)
			{
				if (r.end <= s.end)
					break;

				consumer(r, s);
			}

			itS.moveToNextEndpoint();
			if (itS.isFinished())
				break;
		}
	}
}


