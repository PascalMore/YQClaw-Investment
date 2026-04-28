import sys
sys.argv = ['main.py', '--date', '2026-04-28', '--output', 'email']
exec(open('main.py').read())