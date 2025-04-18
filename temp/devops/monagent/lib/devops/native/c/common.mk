# Directories
TOP := $(dir $(lastword $(MAKEFILE_LIST)))
WORKING_DIR ?= $(shell pwd)
BIN_DIR=$(WORKING_DIR)/bin
LOCAL_INCLUDE_DIR=$(WORKING_DIR)/include
OBJ_DIR=$(WORKING_DIR)/obj
LIB_DIR=$(WORKING_DIR)/lib
SRC_DIR=$(WORKING_DIR)/src

# Print statements
#$(info $(TOP))
#$(info $(WORKING_DIR))
#$(info $(lastword $(MAKEFILE_LIST)))

DELETE_COMMAND=rm -rf

# Compiler to use.
CC=gcc

# Compiler flags
# -g    adds debugging information to the executable file
# -Wall turns on most, but not all, compiler warnings

XFLAGS	= -c -Wall

INCLUDE_DIRS   = -I${LOCAL_INCLUDE_DIR}

CFLAGS    = ${VERSION} ${INCLUDE_DIRS} ${XFLAGS}
SHARED_C_FLAGS    = ${VERSION} ${INCLUDE_DIRS}