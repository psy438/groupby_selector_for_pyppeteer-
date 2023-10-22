import re
from random import choices, randint, uniform
from numpy.random import choice
from numpy import ndarray
import nest_asyncio
from os import environ
from pyppeteer.page import Page
from pyppeteer.element_handle import ElementHandle
from typing import Union, List, Dict, Pattern, Optional, Set, Tuple, TypedDict, Generator, Any
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
    names: List[List[str]] = []
    zhongzhuan = []
    # 按照搜索顺序进行分割
    for i in range(len(or_arrs)):
        arrow_arrs[i] = or_arrs[i].split('[->]')
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


class dict_element_and_children(TypedDict):
    f_name: str
    element: ElementHandle
    s_name: str
    children: List['elementNode']


class elementNode(object):

    def __new__(cls, *args, **kwargs):

        self_in_init = super().__new__(cls)
        cls.id = id(self_in_init)
        return self_in_init

    def __init__(self, name: str, element: ElementHandle, children: List['elementNode']) -> None:
        super().__init__()
        self.name = name
        self.element = element
        self.children: List['elementNode'] = children

    @staticmethod
    def find_elements_by_name(node: 'elementNode', name) -> List[ElementHandle]:
        '''在树中查找所有含有name标签的元素'''
        ans: List[ElementHandle] = []
        que: List['elementNode'] = [node]
        while len(que) > 0:
            n = que.pop(0)
            if n.name == name:
                ans.append(n.element)
            for i in n.children:
                que.append(i)
        return ans

    @staticmethod
    def find_node_by_name(node: 'elementNode', name: str) -> List['elementNode']:
        ans: List['elementNode'] = []
        que: List['elementNode'] = [node]
        while len(que) > 0:
            n = que.pop(0)
            if n.name == name:
                ans.append(n)
            for i in n.children:
                que.append(i)
        return ans

    @staticmethod
    def group_elements_by_name_and_aname(node: 'elementNode', name1: str, name2: str) -> Dict[ElementHandle, List[ElementHandle]]:
        '''查找name1和name2的对应关系,name1为祖先节点,name2为后代节点'''
        ans: Dict[ElementHandle, List[ElementHandle]] = {}
        name1_nodes: List['elementNode'] = elementNode.find_node_by_name(
            node=node, name=name1)
        for node in name1_nodes:
            if node.element not in ans:
                ans[node.element] = []
            ans[node.element] = elementNode.find_elements_by_name(
                node=node, name=name2)
        return ans

    @staticmethod
    def yield_element_children_by_names(node: 'elementNode', name: str) -> Optional[Generator[Any, Any, dict_element_and_children]]:
        '''一个根据name值生成相应元素组和子节点组的生成器'''
        que: List['elementNode'] = [node]
        while len(que) > 0:
            out_node = que.pop(0)
            if out_node.name == name:
                son_names: List[str] = []
                for chil in out_node.children:
                    son_names.append(chil.name)
                yield {'f_name': name, 'element': out_node.element, 's_name': son_names, 'children': out_node.children}
            for child in out_node.children:
                que.append(child)
        return None

    @staticmethod
    def list_all_leaf(node: 'elementNode') -> List['elementNode']:
        '''返回该elementNode树的所有叶子节点'''
        ans: List['elementNode'] = []
        que: List['elementNode'] = [node]
        while len(que) > 0:
            out_node: 'elementNode' = que.pop(0)
            if len(out_node.children) == 0:
                ans.append(out_node)
            for chil in out_node.children:
                que.append(chil)
        return ans

    @staticmethod
    def group_all_nodes_by_all_names(node: 'elementNode') -> Dict[str, List[ElementHandle]]:
        '''根据所有的name标签，形成一个dict[name,list[elementHandle]]字典'''
        ans: Dict[str, List[ElementHandle]] = {}
        que: List['elementNode'] = [node]
        while len(que) > 0:
            out_node = que.pop(0)
            if out_node.name not in ans:
                ans[out_node.name] = [out_node.element]
            else:
                ans[out_node.name].append(out_node.element)
            for chil in out_node.children:
                que.append(chil)
        return ans

    @staticmethod
    async def find_child_node_element_by_selector(node: 'elementNode', name: str, *selectors: str) -> 'elementNode':
        '''根据当前输入的elementNode,形成根据selector表达式变成当前节点的子节点'''
        selector_str: str = ','.join(selectors)
        elements = await node.element.querySelectorAll(selector_str)
        for element in elements:
            this_element = elementNode(
                name=name, element=element, children=[].copy())
            node.children.append(this_element)
        return node

    @staticmethod
    def delete_sons(node: 'elementNode') -> 'elementNode':
        '''删除该elementnode的所有子elementnode,并且返回该节点'''
        node.children = []
        return node

    @staticmethod
    def setP():
        '''用来设置概率'''
        ...


async def groupby_selector_by_dict(page: Page, name_to_selector: Dict[str, str], name_to_name: Dict[str, List[str]]) -> elementNode:
    '''name_to_selector={name:str,selector:str},name_to_name={name:List[aname]}
        键名不能含有空字符串
        只能有一个根节点
        name不能含有字符串
    '''
    # 增加用户没写的name标签
    for name in name_to_selector:
        if name not in name_to_name:
            name_to_name[name] = []

    dict_set: Set[str] = set(name_to_selector.keys())
    has_set: Set[str] = set()  # 不是根目录的name
    for name in name_to_name:
        if name == '':
            raise IndexError("the name can't defind to empty string!!!")
        for n in name_to_name[name]:
            has_set.add(n)
    root_set: Set[str] = dict_set.difference(has_set)
    empty_elementHandle: ElementHandle = await page.evaluate('document.createElement("div")')
    # 创建空elementNode根节点
    rootNode = elementNode(
        name='', element=empty_elementHandle, children=[].copy())
    # 创建队列
    elementNode_que: List[elementNode] = []

    # 将所有的根name连接到rootNode中
    root_list = list(root_set)
    for root_name in root_list:
        root_element = await page.querySelectorAll(name_to_selector[root_name])
        for element in root_element:
            root_elementNode: elementNode = elementNode(
                name=root_name, element=element, children=[].copy())
            rootNode.children.append(root_elementNode)
            elementNode_que.append(root_elementNode)
    # 开始广度优先搜索
    while len(elementNode_que) > 0:
        node = elementNode_que.pop(0)
        for name in name_to_name[node.name]:
            elements = await node.element.querySelectorAll(name_to_selector[name])
            for element in elements:
                chil_elementNode: elementNode = elementNode(
                    name=name, element=element, children=[].copy())
                node.children.append(chil_elementNode)  # 这句有问题
                elementNode_que.append(chil_elementNode)
    return rootNode
