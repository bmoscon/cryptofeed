from typing import List


def in_x_smaller_lists(large_list: list, number_of_lists: int) -> List[list]:
    """
    Split one large list into smaller ones.

    See https://stackoverflow.com/q/752308#11574640
    """
    if not large_list:
        return []
    return [large_list[i::number_of_lists] for i in range(number_of_lists)]


def list_by_max_items(large_list: list, max_items: int) -> List[list]:
    """
    Optimize splitting to get minimal number of smaller lists.

    Each returned smaller list has about the same number of items that is less than or equal to max_items.
    """
    number_of_lists = max(1, len(large_list) // max_items)
    return in_x_smaller_lists(large_list, number_of_lists)
