
#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>

#include "algorithms/IEJoin.h"
#include "model/Relation.h"

Relation readCarryEventsFromFile(const std::string& filename)
{
    Relation relation;
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "CRITICAL ERROR: Cannot open file " << filename << std::endl;
        return relation;
    }
    std::string line;
    while (std::getline(file, line)) {
        if (line.empty()) continue;
        std::stringstream ss(line);
        std::string field;
        Tuple t;
        try {
            std::getline(ss, field, ','); t.id = std::stoi(field);
            std::getline(ss, field, ','); t.person_id = std::stoi(field);
            std::getline(ss, field, ','); t.object_id = std::stoi(field);
            std::getline(ss, field, ','); t.start = static_cast<Timestamp>(std::stol(field));
            std::getline(ss, field, ','); t.end = static_cast<Timestamp>(std::stol(field));
            std::getline(ss, field, ','); t.video_id = std::stoi(field);
            relation.push_back(t);
        } catch (const std::exception& e) {
            std::cerr << "FORMAT ERROR: " << e.what() << " on line: " << line << std::endl;
            continue;
        }
    }
    std::cout << "INFO: Successfully read " << relation.size() << " events from " << filename << std::endl;
    return relation;
}

int main(int argc, const char* argv[])
{
    std::cout << "ISEQL Custom Build for Package Handoff" << std::endl;

    if (argc < 5) {
        std::cerr << "ERROR: Insufficient arguments." << std::endl;
        std::cerr << "Usage: ./iseql handoff <path_to_R> <path_to_S> <delta_frames>" << std::endl;
        return 1;
    }

    std::string command = argv[1];

    if (command == "handoff")
    {
        std::string fileR_path = argv[2];
        std::string fileS_path = argv[3];
        long delta_long = std::stol(argv[4]);
        Timestamp delta = static_cast<Timestamp>(delta_long);

        std::cout << "INFO: Starting 'handoff' process with delta = " << delta << std::endl;

        Relation R = readCarryEventsFromFile(fileR_path);
        Relation S = readCarryEventsFromFile(fileS_path);

        if (R.empty() || S.empty()) {
            std::cerr << "ERROR: One or both input files are empty or unreadable." << std::endl;
            return 1;
        }

        std::cout << "INFO: Executing temporal join..." << std::endl;
        ieJoinBeforeJoin(R, S, delta, [](const Tuple& r, const Tuple& s)
        {
            if (r.video_id != s.video_id) return;
            if (r.object_id != s.object_id) return;
            if (r.person_id == s.person_id) return;

            std::cout << "RISULTATO,"
                      << r.person_id << "," << s.person_id << "," << r.object_id << ","
                      << r.end << "," << s.start << "," << (s.start - r.end) << ","
                      << r.video_id << std::endl; // endl qui
        });
        std::cout << "INFO: 'handoff' process complete." << std::endl;
    }
    else
    {
        std::cerr << "ERROR: Unrecognized command." << std::endl;
        return 1;
    }

    return 0;
}