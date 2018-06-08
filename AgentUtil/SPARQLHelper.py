def filterSPARQLValues(attribute, values, is_string):
    query = "VALUES (" + attribute + ") "

    query += "{ "
    for value in values:
        query += "( "
        query += ('"' + value + '"') if is_string else value
        query += " ) "

    query += "}"
    return query
