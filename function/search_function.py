from fastapi import HTTPException


def deal_range(_range: list[str]):
    """
        search value form {from} to {to} in {column}
    :param _range:
        [
            "column,from,to",
            "time,2022-01-04T12:00:00Z,2022-01-06T12:00:00Z",
            "time,null,2022-01-06T12:00:00Z"
        ]

    :return:
    """
    result = ""
    for item in _range:
        r_list = item.replace(" ", "").split(",")
        if len(r_list) != 3:
            raise HTTPException(status_code=406, detail="query range do not accept")
        if r_list[1] != "null":
            result += f"{r_list[0]} >= '{r_list[1]}' and "
        if r_list[2] != "null":
            result += f"{r_list[0]} <= '{r_list[2]}' and "
    return result


def deal_value_in(_value_in: list[str]):
    """
        search column which in (value1, value2, ...)
    :param _value_in:
        [
            column, value1, value2, ...
        ]

    :return:
    """
    result = ""
    for item in _value_in:
        v_list = item.replace(" ", "").split(",")
        if len(v_list) < 2:
            raise HTTPException(status_code=406, detail="query value in miss some params")
        if len(v_list) == 2:
            result += f"{v_list[0]} in {str(tuple(v_list[1:])).replace(',', '')} and "
        else:
            result += f"{v_list[0]} in {tuple(v_list[1:])} and "
    return result


def deal_json_in(_json_in: list[str]):
    """
        search json column which has value
    :param _json_in:
        [
            column, value
        ]
    :return:
    """
    result = ""
    for item in _json_in:
        j_list = item.replace(" ", "").split(",")
        if len(j_list) != 2:
            raise HTTPException(status_code=406, detail="query json in do not match")
        result += f"json_search(json_extract({j_list[0]}, '$[*]'),'all', '{j_list[1]}') is not null and "
    return result
