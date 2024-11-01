import codecs
from datetime import datetime
import os


def gen_derived_columns(cursor, source):
  command = ""
  print(source)
  source_name, source_object = source.split("_.._")

  query = f"""
              SELECT DISTINCT Source_Column_Physical_Name, Business_Key_Physical_Name
              FROM
              (
              SELECT Source_Column_Physical_Name, Business_Key_Physical_Name
              FROM standard_hub h inner join source_data src on h.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND Source_Column_Physical_Name <> Business_Key_Physical_Name

              UNION
              
              SELECT Source_Column_Physical_Name, Target_Column_Physical_Name AS Business_Key_Physical_Name 
              FROM standard_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND l.Source_Column_Physical_Name <> l.Target_Column_Physical_Name
              AND l.Hub_identifier IS NULL

              UNION
              
              SELECT Source_Column_Physical_Name, Target_Column_Physical_Name AS Business_Key_Physical_Name 
              FROM non_historized_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND l.Source_Column_Physical_Name <> l.Target_Column_Physical_Name
              AND l.Hub_identifier IS NULL                            

              UNION
              
              SELECT Source_Column_Physical_Name, Target_Column_Physical_Name 
              FROM standard_satellite s
              inner join source_data src on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND Source_Column_Physical_Name <> Target_Column_Physical_Name
              
              UNION
              
              SELECT Source_Column_Physical_Name, Target_Column_Physical_Name 
              FROM multiactive_satellite s
              inner join source_data src on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND Source_Column_Physical_Name <> Target_Column_Physical_Name
              )
              order by Business_Key_Physical_Name


       
              
              
              """
  cursor.execute(query)
  results = cursor.fetchall()

  for der_column in results:
    if command == "":
      command = "derived_columns:\n\t"

    source_name = der_column[0]
    target_name = der_column[1]

    command = command + f"\t{target_name}:\n\t\t\tvalue: {source_name}\n\t\t\tsrc_cols_required: {source_name}\n\t"


  return command


def get_groupname(cursor,source_name,source_object):
    query = f"""SELECT DISTINCT GROUP_NAME from source_data 
    where Source_System = '{source_name}' and Source_Object = '{source_object}'
    LIMIT 1"""
    cursor.execute(query)
    return cursor.fetchone()[0]

def gen_hashed_columns(cursor,source, hashdiff_naming):
  
  command = ""
  print(source)
  source_name, source_object = source.split("_.._")

  query = f"""
              SELECT Target_Primary_Key_Physical_Name, GROUP_CONCAT(Source_Column_Physical_Name), IS_SATELLITE FROM 
              (SELECT COALESCE(h.Target_Primary_Key_Physical_Name,h.Target_Primary_Key_Physical_Name) as Target_Primary_Key_Physical_Name, h.Source_Column_Physical_Name, FALSE as IS_SATELLITE
              FROM standard_hub h
              inner join source_data src on h.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              ORDER BY h.Target_Column_Sort_Order) 
              GROUP BY Target_Primary_Key_Physical_Name

              UNION

              SELECT Target_Primary_Key_Physical_Name, GROUP_CONCAT(Source_Column_Physical_Name), IS_SATELLITE FROM
              (SELECT 
              l.Target_Primary_Key_Physical_Name,             
              COALESCE(l.Prejoin_Target_Column_Alias, l.Prejoin_Extraction_Column_Name, l.Source_Column_Physical_Name) as Source_Column_Physical_Name,
              FALSE as IS_SATELLITE
              --(SELECT l.Target_Primary_Key_Physical_Name, l.Source_Column_Physical_Name,FALSE as IS_SATELLITE
              FROM standard_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND l.Target_Primary_Key_Physical_Name IS NOT NULL
              ORDER BY l.Target_Column_Sort_Order)
              group by Target_Primary_Key_Physical_Name
  
              UNION

              SELECT Target_column_physical_name, GROUP_CONCAT(Source_Column_Physical_Name), IS_SATELLITE FROM
              (SELECT DISTINCT l.Target_column_physical_name, l.Source_Column_Physical_Name,FALSE as IS_SATELLITE
              FROM standard_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              inner join standard_hub h on l.Hub_identifier = h.Hub_identifier and l.Target_column_physical_name <> h.Target_Primary_Key_Physical_Name
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND l.Hub_identifier IS NOT NULL
              ORDER BY l.Target_Column_Sort_Order)
              group by Target_column_physical_name
          
              UNION
              
              SELECT Target_Primary_Key_Physical_Name, GROUP_CONCAT(Source_Column_Physical_Name), IS_SATELLITE FROM
              (SELECT 
              l.Hub_primary_key_physical_name as Target_Primary_Key_Physical_Name,             
              COALESCE(l.Prejoin_Target_Column_Alias, l.Prejoin_Extraction_Column_Name) as Source_Column_Physical_Name,
              FALSE as IS_SATELLITE
              FROM standard_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND l.Target_Primary_Key_Physical_Name IS NOT NULL
              and l.Prejoin_Table_Identifier is not NULL
              ORDER BY l.Target_Column_Sort_Order)
              group by Target_Primary_Key_Physical_Name
              
              UNION
              SELECT Target_Satellite_Table_Physical_Name,GROUP_CONCAT(Source_Column_Physical_Name),IS_SATELLITE FROM 
              (SELECT '{hashdiff_naming.replace("@@SatName", "")}' || s.Target_Satellite_Table_Physical_Name as Target_Satellite_Table_Physical_Name,s.Source_Column_Physical_Name,TRUE as IS_SATELLITE
              FROM standard_satellite s
              inner join source_data src on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              order by s.Target_Column_Sort_Order)
              group by Target_Satellite_Table_Physical_Name
              
              UNION
              SELECT DISTINCT Target_Satellite_Table_Physical_Name,Multi_Active_Attributes,IS_SATELLITE FROM 
              (SELECT '{hashdiff_naming.replace("@@SatName", "")}' || s.Target_Satellite_Table_Physical_Name as Target_Satellite_Table_Physical_Name, REPLACE (s.Multi_Active_Attributes, ';',',') AS Multi_Active_Attributes ,TRUE as IS_SATELLITE
              FROM multiactive_satellite s
              inner join source_data src on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              order by s.Target_Column_Sort_Order)          

              UNION
              SELECT DISTINCT Target_Satellite_Table_Physical_Name,GROUP_CONCAT(Source_Column_Physical_Name),IS_SATELLITE FROM 
              (SELECT '{hashdiff_naming.replace("@@SatName", "")}' || s.Target_Satellite_Table_Physical_Name as Target_Satellite_Table_Physical_Name,s.Source_Column_Physical_Name,TRUE as IS_SATELLITE
              FROM non_historized_satellite s
              inner join source_data src on s.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              )
              group by Target_Satellite_Table_Physical_Name

              UNION

              SELECT Target_Primary_Key_Physical_Name, GROUP_CONCAT(Source_Column_Physical_Name), IS_SATELLITE FROM
              (SELECT l.Target_Primary_Key_Physical_Name, l.Source_Column_Physical_Name,FALSE as IS_SATELLITE
              FROM non_historized_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND l.Target_Primary_Key_Physical_Name IS NOT NULL
              ORDER BY l.Target_Column_Sort_Order)
              group by Target_Primary_Key_Physical_Name

              UNION

              SELECT Target_column_physical_name, GROUP_CONCAT(Source_Column_Physical_Name), IS_SATELLITE FROM
              (SELECT l.Target_column_physical_name, l.Source_Column_Physical_Name,FALSE as IS_SATELLITE
              FROM non_historized_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              AND l.Hub_identifier IS NOT NULL
              ORDER BY l.Target_Column_Sort_Order)
              group by Target_column_physical_name
              
              
              """
  cursor.execute(query)
  results = cursor.fetchall()

  for hashkey in results:
  
    hashkey_name = hashkey[0]
    bk_list = hashkey[1].split(",")

    command = command + f"\t{hashkey_name}:\n"

    if hashkey[2]: 
      command = command + "\t\tis_hashdiff: true\n\t\tcolumns:\n"

      for bk in bk_list:
        command = command + f"\t\t\t- {bk}\n"
    
    else:
      for bk in bk_list:
        command = command + f"\t\t- {bk}\n"

  return command


def gen_prejoin_columns(cursor, source):
  
  command = ""  

  source_name, source_object = source.split("_.._")
  
  query = f"""SELECT 
              COALESCE(l.Prejoin_Target_Column_Alias,l.Prejoin_Extraction_Column_Name) as Prejoin_Target_Column_Name,
              pj_src.Source_Schema_Physical_Name,
              pj_src.Source_Table_Physical_Name,
              l.Prejoin_Extraction_Column_Name,
              l.Source_column_physical_name,
              l.Prejoin_Table_Column_Name
              FROM standard_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              inner join source_data pj_src on l.Prejoin_Table_Identifier = pj_src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              and l.Prejoin_Table_Identifier is not NULL
              UNION ALL 
              SELECT 
              COALESCE(l.Prejoin_Target_Column_Alias,l.Prejoin_Extraction_Column_Name) as Prejoin_Target_Column_Name,
              pj_src.Source_Schema_Physical_Name, 
              pj_src.Source_Table_Physical_Name,
              l.Prejoin_Extraction_Column_Name, 
              l.Source_column_physical_name,
              l.Prejoin_Table_Column_Name
              FROM non_historized_link l
              inner join source_data src on l.Source_Table_Identifier = src.Source_table_identifier
              inner join source_data pj_src on l.Prejoin_Table_Identifier = pj_src.Source_table_identifier
              WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
              and l.Prejoin_Table_Identifier is not NULL"""
  
  
  cursor.execute(query)
  prejoined_column_rows = cursor.fetchall()
  for prejoined_column in prejoined_column_rows:

    if command == "":
      command = "prejoined_columns:\n"

    schema = prejoined_column[1]
    table = prejoined_column[2]
    alias = prejoined_column[0]
    bk_column = prejoined_column[3]
    this_column_name = prejoined_column[4]
    ref_column_name = prejoined_column[5]

    command = command + f"""\t{alias}:\n\t\tsrc_name: '{source_name}'\n\t\tsrc_table: '{table}'\n\t\tbk: '{bk_column}'\n\t\tthis_column_name: '{this_column_name}'\n\t\tref_column_name: '{ref_column_name}'\n"""

  return command


def gen_multiactive_columns(cursor,source):
  command = ""
  source_name, source_object = source.split("_.._")
  query = f"""  SELECT DISTINCT Target_column_physical_name, Parent_primary_key_physical_name 
                from multiactive_satellite mas
                inner join source_data src on mas.Source_Table_Identifier = src.Source_table_identifier
                WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
                ORDER BY Target_Column_Sort_Order """
  cursor.execute(query)
  multiactive_column = cursor.fetchall()
  for row in multiactive_column:
    if command == "":
      command = "multiactive_config:\n\tmulti_active_key:\n"
    
    ma_key = row[0]
    parent_hk = row[1]

    for key in ma_key.split(';'):
      command = command + f"\t\t- {key}\n"

  if command != "":
    command = command + f"\tmain_hashkey_column:\n\t- {parent_hk}"

  return command

def generate_stage(cursor, source,generated_timestamp, rdv_default_schema, stage_default_schema, model_path,hashdiff_naming, stage_prefix):

  derived_columns = gen_derived_columns(cursor, source)
  hashed_columns = gen_hashed_columns(cursor, source, hashdiff_naming)
  prejoins = gen_prejoin_columns(cursor, source)
  multiactive = gen_multiactive_columns(cursor,source)
  source_name, source_object = source.split("_.._")
  group_name = get_groupname(cursor,source_name,source_object)
  model_path = model_path.replace("@@GroupName", 'stage').replace("@@SourceSystem", source_name).replace('@@timestamp',generated_timestamp)

  query = f"""SELECT Source_Schema_Physical_Name,Source_Table_Physical_Name, Record_Source_Column, Load_Date_Column, Source_System  FROM source_data src
                WHERE src.Source_System = '{source_name}' and src.Source_Object = '{source_object}'
                """

  cursor.execute(query)
  sources = cursor.fetchall()

  for row in sources: #sources usually only has one row
    source_schema_name = row[0]
    source_table_name = row[1]  
    rs = row[2]
    ldts = row[3]
    source_system_name = row[4]
  timestamp = generated_timestamp
  
  with open(os.path.join(".","templates","stage.txt"),"r") as f:
      command_tmp = f.read()
  f.close()
  command = command_tmp.replace("@@RecordSource",rs).replace("@@LoadDate",ldts).replace("@@HashedColumns", hashed_columns).replace("@@PrejoinedColumns",prejoins).replace('@@SourceName',source_system_name).replace('@@SourceTable',source_table_name).replace('@@SCHEMA',source_schema_name).replace('@@MultiActive',multiactive).replace('@@rdv_schema', rdv_default_schema).replace('@@derived_columns', derived_columns)

  filename = os.path.join(model_path , f"{stage_prefix}{source_table_name.lower()}.sql")
          
  path = os.path.join(model_path)


  # Check whether the specified path exists or not
  isExist = os.path.exists(path)
  if not isExist:   
  # Create a new directory because it does not exist 
      os.makedirs(path)

  with open(filename, 'w') as f:
    f.write(command.expandtabs(2))

  print(f"Created stage model \'{stage_prefix}{source_table_name.lower()}.sql\'")
