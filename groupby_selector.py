import re
import nest_asyncio
from os import environ
from pyppeteer.page import Page
from pyppeteer.element_handle import ElementHandle
from typing import Union, List, Dict, Pattern
nest_asyncio.apply()
environ["CUDA_VISIBLE_DEVICES"] = "-1"

# 有问题,这个根据deep选取的names列表有问题


async def groupby_selector_to_get_element(string: str, page: Page) -> Dict[str, List[List[ElementHandle]]]:
    '''用来创立一个新的表达式，能够通过一种特殊的selector表达式将获取到的页面元素分组'''
    def search_name(pattern: Union[Pattern, str], string: str) -> str:
        p = re.search(pattern=pattern, string=string)
        if p:
            return p.group()
        else:
            return ''
    result = {}
    # 分割字符串成数组
    or_arrs = string.split(sep='[|]')
    arrow_arrs: List[List[str]] = [[].copy()]*len(or_arrs)
    # 按照搜索顺序进行分割
    for i in range(len(or_arrs)):
        arrow_arrs[i] = or_arrs[i].split('[->]')
    names: List[List[str]] = []
    zhongzhuan = []
    for i in range(len(arrow_arrs)):
        for j in range(len(arrow_arrs[i])):
            na = search_name('(?<=lable\().*?(?=\))', arrow_arrs[i][j])
            # 替换name标签
            arrow_arrs[i][j] = re.sub('lable\(.*?\):', '', arrow_arrs[i][j])
            zhongzhuan.append(na)
        names.append(zhongzhuan)
        zhongzhuan = []
    # 将names数组注册到result中
    for nas in names:
        for na in nas:
            result[na] = []
    # 广度优先搜索
    i: int = 0
    while i < len(arrow_arrs):
        el: List[ElementHandle] = await page.querySelectorAll(arrow_arrs[i][0])
        deep: int = 0  # 记录节点的深度
        stack = [[el, deep]]
        need_names: List[str] = names[i]
        while len(stack) > 0:
            element_list, deep = stack.pop(0)
            result[need_names[deep]].append(element_list)
            deep += 1
            # 如果有下一层
            if deep < len(arrow_arrs[i]):
                for element in element_list:
                    stack.append([await element.querySelectorAll(arrow_arrs[i][deep]), deep])
        need_names = []
        i += 1
    return result

