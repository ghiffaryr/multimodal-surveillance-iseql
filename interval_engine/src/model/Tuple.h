#pragma once

#include "Interval.h" // Corretto il percorso
#include <string>
#include <iostream>

struct Tuple : public Interval
{
    // I nostri campi, che corrispondono ai dati CSV
    int id;
    int person_id;
    int object_id;
    int video_id;

    // La nostra funzione di stampa per il debug
    friend std::ostream& operator<<(std::ostream& os, const Tuple& t)
    {
        os << "Event(id=" << t.id << ", p_id=" << t.person_id << ", o_id=" << t.object_id
           << ", v_id=" << t.video_id << ", start=" << t.start << ", end=" << t.end << ")";
        return os;
    }
};