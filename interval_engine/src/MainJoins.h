#pragma once

#include <iostream>
#include <memory>

#include "util/Arguments.h"
#include "util/Experiments.h"
#include "util/Timer.h"
#include "util/Aggregates.h"
#include "model/RelationGenerator.h"
#include "MainCommon.h"
#include "algorithms/IEJoin.h"
#include "algorithms/Joins.h"
#include "algorithms/LMJoins.h"
#include "algorithms/WithTree.h"



typedef void join_algorithm_t(const Relation&, const Relation&, const Workload&);

inline void compareDanilaAndLM(const Relation& R, const Relation& S, Experiments& experiments,
                               join_algorithm_t* danila, join_algorithm_t* lm)
{
	experiments.experiment("danila", "index", [&]
	{
		Timestamp accum = 0;
		danila(R, S, Workload{accum});
		return accum;
	});

	experiments.experiment("lm", "sort", [&]
	{
		Timestamp accum = 0;

		Workload workload{accum};
		lm(R, S, workload);

		#ifdef COUNTERS
		experiments.addExperimentResult("z", static_cast<double>(workload.count));
		#endif

		return accum;
	});
}


template <typename IEJoin, typename CreateIEJoin>
void testIEJoin(Experiments& experiments, CreateIEJoin&& createIEJoin)
{
	std::unique_ptr<IEJoin> ieJoin;

	experiments.prepare("ie-index", "", [&]
	{
		ieJoin.reset(new IEJoin(createIEJoin()));
	});

	experiments.experiment("ie", "ie-index", [&]
	{
		Timestamp accum = 0;
		ieJoin->join(Workload{accum});
		return accum;
	});
}



inline void mainJoins(const std::string& command, Arguments& arguments)
{
	Relation R, S;

	auto experiments = getExperimentsAndPopulateRelations(arguments, R, S);


	experiments.prepare("sort", "", [&]
	{
	    R.sort();
	    S.sort();
	});

	Index indexR{}, indexS{};

	experiments.prepare("index", "sort", [&]
	{
		indexR.buildFor(R);
		indexS.buildFor(S);
	});

	R.setIndex(indexR);
	S.setIndex(indexS);


	if (command == "reverse-during")
	{
		compareDanilaAndLM(R, S, experiments, &reverseDuringStrictJoin,  &leungMuntzReverseDuringStrictJoin);
		testIEJoin<IEJoinReverseDuringStrict>(experiments, [&]
		{
			return createIEJoinReverseDuringStrict(R, S);
		});
		experiments.experiment("tree", "index", [&]
		{
			Timestamp accum = 0;
			reverseDuringStrictJoinWithTree(R, S, Workload{accum});
			return accum;
		});
	}
	else
	if (command == "start-preceding")
	{
		compareDanilaAndLM(R, S, experiments, &startPrecedingStrictJoin, &leungMuntzStartPrecedingStrictJoin);
		testIEJoin<IEJoinStartPrecedingStrict>(experiments, [&]
		{
			return createIEJoinStartPrecedingStrict(R, S);
		});
	}
	else
	if (command == "left-overlap")
	{
		compareDanilaAndLM(R, S, experiments, &leftOverlapStrictJoin,    &leungMuntzLeftOverlapStrictJoin);
	}
	else
	if (command == "before-join")
	{
		Aggregate<Timestamp> stats;
		for (const auto& r : R)
			stats.add(r.getLength());

		auto delta = (Timestamp) stats.getAvg();

		experiments.experiment("danila", "index", [&]
		{
			Timestamp accum = 0;
			beforeJoin(R, S, delta, Workload{accum});
			return accum;
		});

		Relation RSortedByTe = R;
		sortRelationByEnd(RSortedByTe);

		experiments.experiment("lm", "", [&]
		{
			Timestamp accum = 0;

			Workload workload{accum};
			leungMuntzBeforeJoin(RSortedByTe, S, delta, workload);

			#ifdef COUNTERS
			experiments.addExperimentResult("z", static_cast<double>(workload.count));
			#endif

			return accum;
		});


		testIEJoin<IEJoinBefore>(experiments, [&]
		{
			return createIEJoinBefore(R, S, delta);
		});
	}
	else
		arguments.error("Invalid command ", command);





	#ifdef COUNTERS
	experiments.addExperimentResult("lm-sel",   (double) lmCounterAfterSelection / (double) lmCounterBeforeSelection);
//	experiments.addExperimentResult("lm-x-avg", (double) lmCounterActiveCountX / lmCounterActiveCountTimes);
//	experiments.addExperimentResult("lm-y-avg", (double) lmCounterActiveCountY / lmCounterActiveCountTimes);
	experiments.addExperimentResult("lm-avg", (double) (lmCounterActiveCountX + lmCounterActiveCountY) / (double) lmCounterActiveCountTimes);
//	experiments.addExperimentResult("lm-x-max", lmCounterActiveMaxX);
//	experiments.addExperimentResult("lm-y-max", lmCounterActiveMaxY);
	experiments.addExperimentResult("lm-max", (double) lmCounterActiveMax);
	experiments.addExperimentResult("my-sel", myCounterBeforeSelection ? (double) myCounterAfterSelection / (double) myCounterBeforeSelection : 1);
	experiments.addExperimentResult("my-avg", (double) myCounterActiveCount / (double) myCounterActiveCountTimes);
	experiments.addExperimentResult("my-max", (double) myCounterActiveMax);
	experiments.addExperimentResult("lm-comp", (double) (lmComparisonCount + lmCounterBeforeSelection * 2));
	experiments.addExperimentResult("my-comp", (double) myCounterBeforeSelection);
	#endif
}
