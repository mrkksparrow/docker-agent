#ifndef _ZOHO_IF_DETAILS_H
#define _ZOHO_IF_DETAILS_H

#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <linux/ethtool.h>
#include <linux/sockios.h>
#include <errno.h>
#include <unistd.h>
#include <string.h>

int main();
struct ethDetails *getEthernetDetails();

struct ethDetails {
	int ifSpeed;
	int ifIndex;
	int ifErrorCode;
	char *ifName;
	char *ifIpAddress;
	struct ethDetails *next;
};

#endif /* _ZOHO_IF_DETAILS_H */
