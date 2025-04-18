# $Id$
def deleteLinesStartingWithMinusAndRemovePlus(str_inputFilePath, str_outputFilePath):
    input_file_obj = open(str_inputFilePath, 'r')
    output_file_obj = open(str_outputFilePath, 'w')
    str_text = input_file_obj.readlines()
    for i, line in enumerate(str_text):
        if line.startswith('+'):
            #print(line)
            output_file_obj.write(line[1:])
        
        
def main():
    str_inputFilePath = '/home/Jim/repository/zoho/ME_Agent/HEAD/checkin/me_agent/qa/debug_scripts/scrap.py'
    str_outputFilePath = '/home/Jim/repository/zoho/ME_Agent/HEAD/checkin/me_agent/qa/debug_scripts/scrap_corrected.py'
    deleteLinesStartingWithMinusAndRemovePlus(str_inputFilePath, str_outputFilePath)
    
main()