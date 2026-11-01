import ast, os, re
from pathlib import Path


def impact_report(root,symbol):
    from .lessons import lesson_text
    if not symbol or not symbol.isidentifier():raise ValueError('symbol must be an identifier')
    if root.is_symlink() or not root.is_dir():raise ValueError('source root must be an existing nonsymlink directory')
    result={'symbol':symbol,'definitions':[],'calls':[],'references':[],'tests':[],'skipped_files':[],
            'files_examined':0,'truncated':False,
            'warning':'Syntactic/lexical candidates, not resolved bindings or proof of behavior. Confirm using the project LSP and tests.'}
    directories=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        directories+=1
        if directories>64:result['truncated']=True;break
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d not in ('node_modules','target','__pycache__') and not (Path(directory)/d).is_symlink())
        for name in sorted(files):
            path=Path(directory)/name
            if path.suffix not in ('.py','.rs','.js','.ts','.tsx','.go','.java','.cs'):continue
            if result['files_examined']>=64:
                result['truncated']=True
                break
            result['files_examined']+=1
            relative=path.relative_to(root)
            try:text=lesson_text(root,relative)
            except (OSError,UnicodeError):text=None
            if text is None:
                result['skipped_files'].append(str(relative))
                result['truncated']=True
                continue
            hits=[]
            if path.suffix=='.py':
                try:tree=ast.parse(text)
                except (SyntaxError,ValueError):tree=None
                if tree:
                    for node in ast.walk(tree):
                        kind=None
                        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and node.name==symbol:kind='definitions'
                        if isinstance(node,ast.Call) and ((isinstance(node.func,ast.Name) and node.func.id==symbol)
                                                          or (isinstance(node.func,ast.Attribute) and node.func.attr==symbol)):
                            kind='calls'
                        if kind:hits.append((kind,node.lineno))
            for number,line in enumerate(text.splitlines(),1):
                if re.search(r'(?<!\w)'+re.escape(symbol)+r'(?!\w)',line):hits.append(('references',number))
            for kind,number in sorted(set(hits),key=lambda h:(h[1],h[0])):
                record={'path':str(relative),'line':number,'analysis':'python_ast' if kind!='references' else 'lexical'}
                if len(result[kind])<256:result[kind].append(record)
                else:result['truncated']=True
                if ('test' in name.lower() or 'tests' in relative.parts) and record not in result['tests'] and len(result['tests'])<256:
                    result['tests'].append(record)
        if result['truncated']:break
    return result

