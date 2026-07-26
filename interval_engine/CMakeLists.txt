cmake_minimum_required(VERSION 3.10)

if (POLICY CMP0048)
  cmake_policy(SET CMP0048 NEW)
endif (POLICY CMP0048)

project(iseql-cpp CXX)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14")

#set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -D_LIBCPP_DEBUG=0 -D_LIBCPP_DEBUG2=0")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wpedantic -Wall -Wextra -Wconversion -Wdisabled-optimization")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-unknown-pragmas")
if (CMAKE_CXX_COMPILER_ID MATCHES "Clang")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Weverything")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-date-time")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-shadow")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-c++98-compat")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-c++98-compat-pedantic")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-old-style-cast")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-float-equal")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-padded")
endif()



OPTION(COUNTERS "Enable algorithm performance counters" OFF)
if (COUNTERS)
	message("## Enabling counters ##")
	add_definitions(-DCOUNTERS)
endif()

OPTION(EBI "Enable EBI algorithm instead of LEBI" OFF)
if (EBI)
	message("## Enabling EBI ##")
	add_definitions(-DEBI)
endif()


add_subdirectory(src)

