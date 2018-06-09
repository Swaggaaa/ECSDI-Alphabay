import SPARQLWrapper

import AgentUtil.Agents


def filterSPARQLValues(attribute, values, is_string):
    query = "VALUES (" + attribute + ") "

    query += "{ "
    for value in values:
        query += "( "
        query += ('"' + value + '"') if is_string else value
        query += " ) "

    query += "}"
    return query


def read_query(query):
    sparql = SPARQLWrapper.SPARQLWrapper(AgentUtil.Agents.endpoint_read)
    sparql.setCredentials(user='admin', passwd='admin')
    sparql.setReturnFormat(SPARQLWrapper.JSON)
    sparql.setQuery(query)
    return sparql.query().convert()

def update_query(query):
    sparql = SPARQLWrapper.SPARQLWrapper(AgentUtil.Agents.endpoint_update)
    sparql.setCredentials(user='admin', passwd='admin')
    sparql.setReturnFormat(SPARQLWrapper.JSON)
    sparql.setQuery(query)
    return sparql.query().convert()
