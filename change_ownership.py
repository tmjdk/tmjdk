#####################################################################################################################################
#																																	#
#								Change Owner and/or responsible in SOLDOC (PM1)	/by TILT											#
#																																	#
#       This script changes the owner and/or responsible of documents in SAP Solution Documentation (SOLDOC).						#
#		When a person leaves the company you can set a new owner on all documents that this person is owning/responsible for.		#
#		This script will show a "before" and a "after", both in simulation and in live run.											#
#		to save the output from this script just call it with ">somefile.txt" 														#
#														(eks. change_ownership.py>output_change_ownership.txt)						#
#																																	#
#***********************************************************************************************************************************#
#                The script needs 5 inputs 																							#
#																																	#
#				1. SAP User that runs the script 																					#
#				2. Password of the user that runs the script 																		#
#				3. Business partner ID's of the person that leaves 							 										#
#				4. Business partner ID's of the person that takes over 																#
#	   			5. Run simulation (default) or real update (r)																		#
#																																	#
#				NB! As default this script runs as a simulation - Input "r" for the actual run when asked.							#
#																																	#
########################################### - torben.moberg.joergensen@coop.dk - ####################################################

import json
import requests
import re
import pprint

#set the system NB! NB! NB! must be deleted if this script is shared outside COOP
host = 'sappm1ap1.intra.coop'    #PM1 SolMan Hostname 
#host = 'sapdm1ms.dev.intra.coop'    #DM1 SolMan Hostname 
port = '8080'  #ICM Port 
sap_client = '001'  #Active Client with Solution
user = input('\nPlease Enter a SAP User for ' + host + ': ')
passwd = input('Please Enter Password for ' + user + ': ')

#set user/passw for simulation
if user == '' : user = 'admvr0jq' # here you can enter User name for simulation
if passwd == '' : passwd = 'sapTilt1(' # here you can enter Password for simulation

solution_name = 'Z_COOPONE' #Production Solution PM1
# in DM1 solution_name = 'BPCA_POC' #Solution Name ECC_SCOOP  BPCA_POC ZTEST_SCOOP
branch_name = 'MAINTENANCE' #Branch Name

#Check connection and retrieve token
client = requests.session()
headers = {'X-CSRF-Token': 'Fetch', 'Accept': 'application/json', 'Content-Type': 'application/json'}
try:
    response = client.get('http://' + host + ':' + port + '/sap/opu/odata/sap/ProcessManagement?sap-client=' + sap_client, auth=(user, passwd), headers=headers)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print('Connection unsuccessful:\n', e)
    exit(1)
token = response.headers['x-csrf-token']
print('\nConnection successful. Received token:', token + '\n')

# Run as simulation (default=true)
SIMULATION_ONLY = True # simulate first (no import), then change this flag to False to perform actual import
ask_sim = input('Do you want to run the update(r) or just simulate? \nDefault is simulate. Enter r to update: ')
if ask_sim == 'r': SIMULATION_ONLY = False 
if SIMULATION_ONLY: print('\nSIMULATION_ONLY -- NO UPDATE IS PEFORMED!\n')

# Set business partner for simulation
current_bpid = '0000000381'
replace_bpid = '0000000181'

# Get the input, current and leaving BP-id and convert it to 10 digits
if not SIMULATION_ONLY :
	zcurrent_bpid = str(input("Enter current owners Business Partner id: "))
	current_bpid = zcurrent_bpid.zfill(10) 
	zreplace_bpid = str(input("Enter replacement Business Partner id :"))
	replace_bpid = zreplace_bpid.zfill(10)
print('Current Business Partner Id:' + current_bpid + '\t Replacement Business Partner Id:' + replace_bpid + '\n')
print('Please wait while content is being collected ...', end='')

# Later a check of the BP can be added (but I can't for the heck of it figure out why ODATA is failing on DM1 :-/)
def check_bp(uname):
	response = requests.get('http://'+ host + ':' + port + '/sap/opu/odata/SAP/API_BUSINESS_PARTNER/A_BusinessPartner(BusinessPartner=\'' + uname + '\'')
	return list(response.json()['d']['results'])
	
# Selection criteria (which nodes to update?)
select_obj_type = 'KWOBJ' # object type i.e. DOCUMENT, KWOBJ=Document, TESTDOCUMENT, PROC...


#************************************ Buckle your seatbelt Dorothy, cause Kansas is going bye-bye! **********************************# 
# My functions
def get_solution_by_name (solution_name):
    # returns a list of solutions by name
    response = requests.get('http://'+ host + ':' + port + '/sap/opu/odata/sap/ProcessManagement/SolutionSet?sap-client=' + sap_client, auth=(user, passwd), headers=headers)
    return list(filter(lambda s: s['SolutionName'] == solution_name, response.json()['d']['results']))
    
def get_branch_by_name (solution_id, branch_name):
    # returns a list of branches by name and solution_id
    response = requests.get('http://'+ host + ':' + port + '/sap/opu/odata/sap/ProcessManagement/BranchSet?sap-client=' + sap_client, auth=(user, passwd), headers=headers)
    return list(filter(lambda b: b['BranchName'] == branch_name and b['SolutionId'] == solution_id, response.json()['d']['results']))
    
def get_node_attribute_values(my_node, attribute_name):
    # returns the value of an attribute of a node_id
    res = []
    for my_attribute in my_node['attributes']:
        if my_attribute['attr_type'] == attribute_name: res = my_attribute['values']
    return res

# get solution id (by name), branch id (by name)
solution_id = get_solution_by_name(solution_name)[0]['SolutionId']
branch_id = get_branch_by_name(solution_id, branch_name)[0]['BranchId']

# collecting the dataset
print('Fetching branch content...', end='')
response = client.get('http://'+ host + ':' + port + '/sap/opu/odata/sap/ProcessManagement/BranchContentSet(BranchId=\'' + branch_id + '\',ScopeId=\'SAP_DEFAULT_SCOPE\',SiteId=\'\',SystemRole=\'D\')/$value?sap-client=' + sap_client ,auth=(user, passwd),headers=headers)
branch_content = response.json()
print('done.')
#print(branch_content)   # see what we got from that fetch (used for debug)
match_counter = 0  #start counting what we got

# get the section-content of the NODES section...
for section in branch_content['sections']:
	if section['section-id'] == 'NODES':
		nodes_list = json.loads(section['section-content'])  # json-de-code section-content, as it is a string with an extra layer of json-encoding
        # ... and check for each node whether it matches the selection criteria
		for my_node in nodes_list:
			if my_node['obj_type'] == select_obj_type: # object tye matches selection criteria?
				if str(get_node_attribute_values(my_node, '_SMD_RESPONSIBLE')) == '[\'' + current_bpid + '\']' or str(get_node_attribute_values(my_node, 'TEAMMEMBERID')) == '[\'' + current_bpid + '\']': # user matches  selection criteria?
					match_counter-=-1  #;-)
					print('\nFile name:' + str(get_node_attribute_values(my_node, '_DESCRIPTION')), 'Owner:'+ str(get_node_attribute_values(my_node, '_SMD_RESPONSIBLE')), 'Responsible:' + str(get_node_attribute_values(my_node, 'TEAMMEMBERID')))
					# ...if there is a match: update the node
					print('Match ' + str(match_counter) + ' (before): \n' + str(my_node) + '\n')
					# To target the dictionary we want (having attr__type = _SMD_RESPONSIBLE) we need its index in the list.
					if not get_node_attribute_values(my_node, '_SMD_RESPONSIBLE') == []:
						if get_node_attribute_values(my_node, '_SMD_RESPONSIBLE')[0] == current_bpid:
							attr_smd_owner_index = next((index for (index, attribute) in enumerate(my_node['attributes']) if attribute["attr_type"] == "_SMD_RESPONSIBLE"), None)
							my_node['attributes'][attr_smd_owner_index]['values'] = [replace_bpid]
					# again (having attr__type = TEAMMEMBERID) we need its index in the list.
					if not get_node_attribute_values(my_node, 'TEAMMEMBERID') == []:
						if get_node_attribute_values(my_node, 'TEAMMEMBERID')[0]== current_bpid:
							attr_smd_responsible_index = next((index for (index, attribute) in enumerate(my_node['attributes']) if attribute["attr_type"] == "TEAMMEMBERID"), None)
							my_node['attributes'][attr_smd_responsible_index]['values'] = [replace_bpid]
					print('Match ' + str(match_counter) + ' (after): \n' + str(my_node))
				
		print('\nTotal matching nodes found: ' + str (match_counter))
		section['section-content'] = json.dumps(nodes_list) # json-re-encode modified section-content

if SIMULATION_ONLY:
    print('\n Simulation only --> skipping Import.')
    exit(0)

if match_counter == 0: 
 print('Nothing found to be updated. Please run script again and check your input one more time.')
 exit(0)

# Ready to update -- LAST CHANCE TO REGRET!! 
if input('NB! Data is about to get updated with the above!\nAre you sure that you want to continue?\nEnter y continue:') == 'y' :

 # this is not a simulation run and last chance warning has been ignored: import changes to solution manager
 change_document_id = ' '
 url = 'http://'+ host + ':' + port + '/sap/opu/odata/sap/ProcessManagement/BranchContentImporterSet(BranchId=\'' + branch_id + '\',ChangeDocumentId=\'' + change_document_id + '\')/$value'
 data = json.dumps(branch_content)
 headers = {'X-CSRF-Token': token, 'Accept': 'application/json', 'Content-Type': 'application/json'}

 print('\n Importing modified branch content (expecting http 204)...: ', end='')
 response = client.put(url, data=data, headers=headers)
 print(response)

#***************************-FINE-*****-THE END-*****-SLUT-*****-DONE-*****-CU-**********************************************************#