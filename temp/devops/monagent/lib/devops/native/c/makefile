include common.mk
	
$(OBJ_DIR)/ifdetails.o : $(SRC_DIR)/ifdetails.c
	$(CC) ${CFLAGS} -c -o $(OBJ_DIR)/ifdetails.o $(SRC_DIR)/ifdetails.c

ifdetails : $(OBJ_DIR)/ifdetails.o
	$(CC) $(OBJ_DIR)/ifdetails.o -o $(BIN_DIR)/ifdetails
	$(CC) ${SHARED_C_FLAGS} -shared -Wl,-soname,libnic -o $(LIB_DIR)/libnic.so -fPIC $(SRC_DIR)/ifdetails.c

clean:
	$(DELETE_COMMAND) $(OBJ_DIR)/* $(BIN_DIR)/* $(LIB_DIR)/*
	
