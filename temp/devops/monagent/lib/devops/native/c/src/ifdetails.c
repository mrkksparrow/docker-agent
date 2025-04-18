#include<ifdetails.h>

//	http://blog.markloiseau.com/2012/02/get-network-interfaces-in-c/
//	http://amebasystems.googlecode.com/svn-history/r179/research/a-i/isys/ethtool.c
/*
void _init()
{
	printf("Inside _init()\n");
}
void _fini()
{
	printf("Inside _fini()\n");
}
*/

int main()
{
	struct ethDetails *ethDetailsPtr = NULL;
	ethDetailsPtr = (struct ethDetails*)getEthernetDetails();
	while (ethDetailsPtr != NULL)
	{
		printf("ifName %s ",ethDetailsPtr->ifName);
		printf("ifIndex %d ",ethDetailsPtr->ifIndex);
		printf("ifSpeed %d ",ethDetailsPtr->ifSpeed);
		printf("ifErrorCode : %d ",ethDetailsPtr->ifErrorCode);
		printf("\n");
		ethDetailsPtr = ethDetailsPtr->next;
	}
	return 1;
}

/*
 * Returns ethDetails structure.
 * Invoking methods must free ethDetails->ifName, ethDetails->ipAddress and ethDetails.
 *
 */

struct ethDetails *getEthernetDetails()
{
	int sockHandle;
	int i;
	int noOfInterfaces = 0;
	int ifSpeed = 0;
	int ifIndex = 0;
	int errorCode = 0;
	char *ifName = NULL;
	char *ipAddress = NULL;
	char buf[1024];
	struct ifconf ifc;
	struct ifreq *ifr = NULL;

	struct ethDetails *ptrEthDet = NULL;
	struct ethDetails *rootNode = NULL;


	printf("====================== Loading library for fetching ethernet details ====================== \n");

	/* Get a socket handle. */
	sockHandle = socket(AF_INET, SOCK_DGRAM, 0);
	if(sockHandle < 0)
	{
		errorCode = errno;
		printf("Error while fetching socket handle, Error code : %d\n", errorCode);
		return ptrEthDet;
	}

	/* Query available interfaces. */
	ifc.ifc_len = sizeof(buf);
	ifc.ifc_buf = buf;
	if(ioctl(sockHandle, SIOCGIFCONF, &ifc) < 0)
	{
		errorCode = errno;
		printf("Error while querying SIOCGIFCONF for interface list, Error code : %d\n", errorCode);
		return ptrEthDet;
	}

	/* Iterate through the list of interfaces. */
	ifr         = ifc.ifc_req;
	noOfInterfaces = ifc.ifc_len / sizeof(struct ifreq);
	printf("Number of interfaces : %d\n", noOfInterfaces);
	for(i = 0; i < noOfInterfaces; i++)
	{
		int ifErrorCode = 0;
		struct ethDetails *tempNode = NULL;
		struct sockaddr_in *sockaddr = NULL;
		struct ethtool_cmd *ethtoolCmd = NULL;
		struct ifreq *item = &ifr[i];
		/* Interface name */
		ifName = (char *)malloc((strlen(item->ifr_name)+1) * sizeof(char));
		strcpy(ifName, item->ifr_name);
		/* Interface IP address */
		sockaddr = (struct sockaddr_in *)&item->ifr_addr;
		ipAddress = (char *)malloc((strlen(inet_ntoa(sockaddr->sin_addr))+1) * sizeof(char));
		strcpy(ipAddress, inet_ntoa(sockaddr->sin_addr));

		ethtoolCmd = (struct ethtool_cmd*)malloc(sizeof(struct ethtool_cmd));
		ethtoolCmd->cmd = ETHTOOL_GSET;
		item->ifr_data = (void *)ethtoolCmd;

		/* Get interface speed */
		if (ioctl(sockHandle, SIOCETHTOOL, item) >= 0)
		{
			ifSpeed = ethtool_cmd_speed(ethtoolCmd);
		}
		else
		{
			if (errno == EOPNOTSUPP)
			{
				ifSpeed = 0;
			}
			else
			{
				ifErrorCode = errno;
			}
			printf("Error while querying SIOCETHTOOL for fetching interface %s speed. Error code : %d SIOCETHTOOL ioctl : \n",ifName, ifErrorCode);
		}

		/* Get if index */
		if (ioctl(sockHandle, SIOCGIFINDEX, item) >= 0)
		{
			ifIndex = item->ifr_ifindex;
		}
		else
		{
			printf("Error while querying SIOCGIFINDEX for fetching interface %s index. Error code : %d SIOCETHTOOL ioctl : \n",ifName, ifErrorCode);
		}

		/* Get the MAC address
		if(ioctl(sockHandle, SIOCGIFHWADDR, item) < 0)
		{
			perror("ioctl(SIOCGIFHWADDR)");
			ifErrorCode = errno;
		}
		*/
		/* Get the broadcast address*/
		/*
		if(ioctl(sockHandle, SIOCGIFBRDADDR, item) >= 0)
		{
			printf(", BROADCAST %s", inet_ntoa(((struct sockaddr_in *)&item->ifr_broadaddr)->sin_addr));
		}
		*/

		/* Populate details in structure */
		tempNode = (struct ethDetails*)malloc(sizeof(struct ethDetails));
		memset(tempNode, 0, sizeof(struct ethDetails));
		tempNode->ifName = ifName;
		tempNode->ifSpeed = ifSpeed;
		tempNode->ifIndex = ifIndex;
		tempNode->ifErrorCode = ifErrorCode;
		tempNode->ifIpAddress = ipAddress;
		tempNode->next = NULL;
		if(ptrEthDet == NULL)
		{
			rootNode = tempNode;
			ptrEthDet = tempNode;
		}
		else
		{
			ptrEthDet->next = tempNode;
			ptrEthDet = tempNode;
		}
		printf("INTERFACE DETAILS ==> ");
		printf("Name : %s, ",tempNode->ifName);
		printf("IpAddress : %s, ",tempNode->ifIpAddress);
		printf("Index : %d, ",tempNode->ifIndex);
		printf("Bandwidth : %d, ",tempNode->ifSpeed);
		printf("ifErrorCode : %d, ",tempNode->ifErrorCode);
		printf("\n");
		printf("Releasing resources.\n");
		if(ethtoolCmd != NULL)
		{
			free(ethtoolCmd);
		}
	}
	printf("Releasing socket resources.\n");
	close(sockHandle);
	return rootNode;
}
