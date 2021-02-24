#!/usr/bin/env python3

# print('__file__={0:<35} | __name__={1:<20} | __package__={2:<20}'.format(__file__, __name__, str(__package__)))

# import comtypes.client
# comtypes.client.gen_dir = None
# import pywinauto

from ctypes import windll
import argparse
import overlay_arrows_and_more as oaam
from os.path import isfile as os_path_isfile
from sys import exit as sys_exit
from pathlib import Path
import os
import win32api
import win32con
import win32gui_struct
import win32gui
import win32ui


class SysTrayIcon(object):
	QUIT = 'QUIT'
	SPECIAL_ACTIONS = [QUIT]
	FIRST_ID = 1023
	
	def __init__(self, icon, hover_text, menu_options, on_quit=None, default_menu_index=None, window_class_name=None, ):
		self.menu = None
		self.icon = icon
		self.hover_text = hover_text
		self.on_quit = on_quit
		
		menu_options = menu_options + [['Quit', icon_power, self.QUIT], ]
		self._next_action_id = self.FIRST_ID
		self.menu_actions_by_id = set()
		self.menu_options = self._add_ids_to_menu_options(list(menu_options))
		self.menu_actions_by_id = dict(self.menu_actions_by_id)
		del self._next_action_id
		
		self.default_menu_index = (default_menu_index or 0)
		self.window_class_name = window_class_name or "SysTrayIconPy"
		
		message_map = {win32gui.RegisterWindowMessage("TaskbarCreated"): self.restart,
		               win32con.WM_DESTROY: self.destroy,
		               win32con.WM_COMMAND: self.command,
		               win32con.WM_USER + 20: self.notify,}
		# Register the Window class.
		window_class = win32gui.WNDCLASS()
		hinst = window_class.hInstance = win32gui.GetModuleHandle(None)
		window_class.lpszClassName = self.window_class_name
		window_class.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
		window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
		window_class.hbrBackground = win32con.COLOR_WINDOW
		window_class.lpfnWndProc = message_map  # could also specify a wndproc.
		classAtom = win32gui.RegisterClass(window_class)
		# Create the Window.
		style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
		self.hwnd = win32gui.CreateWindow(classAtom, self.window_class_name, style, 0, 0,
		                                  win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT, 0, 0, hinst, None)
		win32gui.UpdateWindow(self.hwnd)
		self.notify_id = None
		self.refresh_icon()
		win32gui.PumpMessages()

	def _add_ids_to_menu_options(self, menu_options):
		result = []
		for menu_option in menu_options:
			option_text, option_icon, option_action = menu_option
			if callable(option_action) or option_action in self.SPECIAL_ACTIONS:
				self.menu_actions_by_id.add((self._next_action_id, option_action))
				result.append(menu_option + [self._next_action_id, ])
			elif non_string_iterable(option_action):
				result.append([option_text,
				               option_icon,
				               self._add_ids_to_menu_options(option_action),
				               self._next_action_id])
			else:
				print('Unknown item', option_text, option_icon, option_action)
			self._next_action_id += 1
		return result
	
	def refresh_icon(self):
		# Try and find a custom icon
		hinst = win32gui.GetModuleHandle(None)
		if os.path.isfile(self.icon):
			icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
			hicon = win32gui.LoadImage(hinst, self.icon, win32con.IMAGE_ICON, 0, 0, icon_flags)
		else:
			print("Can't find icon file - using default.")
			hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
		if self.notify_id:
			message = win32gui.NIM_MODIFY
		else:
			message = win32gui.NIM_ADD
		self.notify_id = (self.hwnd, 0, win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
		                  win32con.WM_USER + 20, hicon, self.hover_text)
		win32gui.Shell_NotifyIcon(message, self.notify_id)

	def restart(self, hwnd, msg, wparam, lparam):
		self.refresh_icon()

	def destroy(self, hwnd, msg, wparam, lparam):
		print("destroy--->")
		if self.on_quit:
			self.on_quit(self)
		nid = (self.hwnd, 0)
		win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
		win32gui.PostQuitMessage(0)  # Terminate the app.
		print("<----destroy")

	def notify(self, hwnd, msg, wparam, lparam):
		if lparam == win32con.WM_LBUTTONDBLCLK:
			self.execute_menu_option(self.default_menu_index + self.FIRST_ID)
		elif lparam == win32con.WM_RBUTTONUP:
			self.show_menu()
		elif lparam == win32con.WM_LBUTTONUP:
			pass
		
		return True
	
	def show_menu(self):
		self.menu = win32gui.CreatePopupMenu()
		self.create_menu(self.menu, self.menu_options)
		# win32gui.SetMenuDefaultItem(menu, 1000, 0)
		pos = win32gui.GetCursorPos()
		win32gui.SetForegroundWindow(self.hwnd)
		win32gui.TrackPopupMenu(self.menu, win32con.TPM_LEFTALIGN, pos[0], pos[1], 0, self.hwnd, None)
		win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

	def create_menu(self, menu, menu_options):
		for option_text, option_icon, option_action, option_id in menu_options[::-1]:
			if option_icon:
				option_icon = self.prep_menu_icon(option_icon)
			if option_id in self.menu_actions_by_id:
				item, _ = win32gui_struct.PackMENUITEMINFO(text=option_text, hbmpItem=option_icon, wID=option_id)
				if option_text == '- - - - - -':
					win32gui.InsertMenu(menu, 0, win32con.MF_SEPARATOR | win32con.MF_BYPOSITION, 0, None)
				else:
					win32gui.InsertMenuItem(menu, 0, 1, item)
			else:
				submenu = win32gui.CreatePopupMenu()
				self.create_menu(submenu, option_action)
				item, _ = win32gui_struct.PackMENUITEMINFO(text=option_text, hbmpItem=option_icon, hSubMenu=submenu)
				if option_text == '- - - - - -':
					win32gui.InsertMenu(menu, 0, win32con.MF_SEPARATOR | win32con.MF_BYPOSITION, 0, None)
				else:
					win32gui.InsertMenuItem(menu, 0, 1, item)

	def prep_menu_icon(self, icon):
		# First load the icon.
		ico_x = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
		ico_y = win32api.GetSystemMetrics(win32con.SM_CYSMICON)
		hIcon = win32gui.LoadImage(0, icon, win32con.IMAGE_ICON, ico_x, ico_y, win32con.LR_LOADFROMFILE)
		hwndDC = win32gui.GetWindowDC(self.hwnd)
		dc = win32ui.CreateDCFromHandle(hwndDC)
		memDC = dc.CreateCompatibleDC()
		iconBitmap = win32ui.CreateBitmap()
		iconBitmap.CreateCompatibleBitmap(dc, ico_x, ico_y)
		oldBmp = memDC.SelectObject(iconBitmap)
		brush = win32gui.GetSysColorBrush(win32con.COLOR_MENU)
		win32gui.FillRect(memDC.GetSafeHdc(), (0, 0, ico_x, ico_y), brush)
		win32gui.DrawIconEx(memDC.GetSafeHdc(), 0, 0, hIcon, ico_x, ico_y, 0, 0, win32con.DI_NORMAL)
		memDC.SelectObject(oldBmp)
		memDC.DeleteDC()
		win32gui.ReleaseDC(self.hwnd, hwndDC)
		return iconBitmap.GetHandle()
	
	def command(self, hwnd, msg, wparam, lparam):
		print("command--->")
		id = win32gui.LOWORD(wparam)
		self.execute_menu_option(id)
		print("<---command")

	def execute_menu_option(self, id):
		menu_action = self.menu_actions_by_id[id]
		if menu_action == self.QUIT:
			win32gui.DestroyWindow(self.hwnd)
		else:
			menu_action(self)


def non_string_iterable(obj):
	try:
		iter(obj)
	except TypeError:
		return False
	else:
		return not isinstance(obj, str)


def overlay_add_pywinauto_recorder_icon(overlay, x, y):
	overlay.add(
		geometry=oaam.Shape.rectangle, x=x, y=y, width=200, height=100, thickness=5, color=(200, 66, 66),
		brush=oaam.Brush.solid, brush_color=(255, 254, 255))
	overlay.add(
		geometry=oaam.Shape.rectangle, x=x + 5, y=y + 15, width=190, height=38, thickness=0,
		brush=oaam.Brush.solid, brush_color=(255, 254, 255), text_color=(66, 66, 66),
		text=u'PYWINAUTO', font_size=44, font_name='Impact')
	overlay.add(
		geometry=oaam.Shape.rectangle, x=x + 20, y=y + 50, width=160, height=38, thickness=0,
		brush=oaam.Brush.solid, brush_color=(255, 254, 255), text_color=(200, 40, 40),
		text=u'recorder', font_size=48, font_name='Arial Black')


def display_splash_screen():
	dir_path = os.path.dirname(os.path.realpath(__file__))
	hicon_light_on = oaam.load_png(dir_path + r'\pywinauto_recorder\light_on.png', 41, 41)
	hicon_light_off = oaam.load_png(dir_path + r'\pywinauto_recorder\light_off.png', 41, 41)
	
	splash_foreground = oaam.Overlay(transparency=0.0)
	time.sleep(0.2)
	splash_background = oaam.Overlay(transparency=0.1)
	screen_width = GetSystemMetrics(0)
	screen_height = GetSystemMetrics(1)
	nb_band = 24
	line_height = 22.5
	text_lines = [''] * nb_band
	text_lines[6] = 'Pywinauto recorder ' + __version__
	text_lines[7] = 'by David Pratmarty'
	text_lines[9] = 'CTRL+ALT+R : Pause / Record / Stop'
	text_lines[11] = 'Search algorithm speed'
	text_lines[13] = 'CTRL+SHIFT+S : Smart mode On / Off'
	text_lines[15] = 'CTRL+SHIFT+F : Copy element path in clipboard'
	text_lines[17] = 'CTRL+ALT+Q : Quit'
	text_lines[19] = 'Drag and drop a recorded file on '
	text_lines[20] = 'pywinauto_recorder.exe to replay it'
	
	splash_background.clear_all()
	w, h = 640, 540
	x, y = screen_width / 2 - w / 2, screen_height / 2 - h / 2
	splash_width = w
	splash_height = h
	splash_left = x
	splash_right = x + w
	splash_top = y
	splash_bottom = y + h
	splash_background.add(
		geometry=oaam.Shape.triangle, thickness=0,
		xyrgb_array=((x, y, 200, 0, 0), (x + w, y, 0, 128, 0), (x + w, y + h, 0, 0, 155)))
	splash_background.add(
		geometry=oaam.Shape.triangle, thickness=0,
		xyrgb_array=((x + w, y + h, 0, 0, 155), (x, y + h, 22, 128, 66), (x, y, 200, 0, 0)))
	
	splash_background.refresh()
	
	mouse_was_splash_screen = False
	x, y = win32api.GetCursorPos()
	if (splash_left < x < splash_right) and (splash_top < y < splash_bottom):
		mouse_was_splash_screen = True
		message_to_continue = 'To continue: move the mouse cursor out of this splash screen'
	else:
		message_to_continue = 'To continue: move the mouse cursor over this splash screen'
	
	py_rec_icon_rect = (splash_left + splash_width / 2 - 200 / 2, splash_top + 30, 200, 100)
	overlay_add_pywinauto_recorder_icon(splash_background, py_rec_icon_rect[0], py_rec_icon_rect[1])
	continue_after_splash_screen = True
	n = 0
	while continue_after_splash_screen:
		splash_foreground.clear_all()
		i = 0
		while i < nb_band:
			if i < 2:
				font_size = 44
			else:
				font_size = 20
			splash_foreground.add(
				x=splash_left, y=splash_top + i * line_height, width=splash_width, height=line_height,
				text=text_lines[i], font_size=font_size, text_color=(254, 255, 255), color=(255, 255, 255),
				geometry=oaam.Shape.rectangle, thickness=0
			)
			i = i + 1
		if n % 6 in [0, 1]:
			overlay_add_record_icon(
				splash_foreground, splash_left + 99, splash_top + line_height * 8.6)
		if n % 6 in [2, 3]:
			overlay_add_pause_icon(
				splash_foreground, splash_left + 99, splash_top + line_height * 8.6)
		if n % 6 in [4, 5]:
			overlay_add_stop_icon(
				splash_foreground, splash_left + 99, splash_top + line_height * 8.6)
		overlay_add_progress_icon(
			splash_foreground, n % 5, splash_left + 99, splash_top + line_height * 10.6)
		overlay_add_play_icon(
			splash_foreground, splash_left + 99, int(splash_top + line_height * 19.1))
		if n % 4 == 0 or n % 4 == 1:
			overlay_add_search_mode_icon(splash_foreground, hicon_light_off, int(splash_left + 99),
			                             int(splash_top + line_height * 12.6))
		else:
			overlay_add_search_mode_icon(splash_foreground, hicon_light_on, int(splash_left + 99),
			                             int(splash_top + line_height * 12.6))
		splash_foreground.refresh()
		time.sleep(0.4)
		if n % 2 == 0:
			text_lines[22] = message_to_continue
		else:
			text_lines[22] = ''
		continue_after_splash_screen = False
		x, y = win32api.GetCursorPos()
		if (splash_left < x < splash_right) and (splash_top < y < splash_bottom):
			if mouse_was_splash_screen:
				continue_after_splash_screen = True
		else:
			if not mouse_was_splash_screen:
				continue_after_splash_screen = True
		n = n + 1
	
	splash_foreground.clear_all()
	splash_foreground.refresh()
	splash_background.clear_all()
	splash_background.refresh()


if __name__ == '__main__':
	windll.user32.ShowWindow(windll.kernel32.GetConsoleWindow(), 6)
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"filename", metavar='path', help="replay a python script", type=str, action='store', nargs='?', default='')
	parser.add_argument(
		"--no_splash_screen", help="Does not display the splash screen", action='store_true')
	args = parser.parse_args()
	if args.filename:
		main_overlay = oaam.Overlay(transparency=0.5)
		from pywinauto_recorder.recorder import overlay_add_play_icon
		import traceback
		import codecs
		
		overlay_add_play_icon(main_overlay, 10, 10)
		if os_path_isfile(args.filename):
			with codecs.open(args.filename, "r", encoding='utf-8') as python_file:
				data = python_file.read()
			print("Replaying: " + args.filename)
			try:
				compiled_code = compile(data, '<string>', 'exec')
				exit_code = eval(compiled_code)
			except Exception as e:
				windll.user32.ShowWindow(windll.kernel32.GetConsoleWindow(), 3)
				exc_type, exc_value, exc_traceback = sys.exc_info()
				output = traceback.format_exception(exc_type, exc_value, exc_traceback)
				for line in output:
					if 'SyntaxError' in output[-1]:
						if not '.py' in line:
							if 'File "<string>", line ' in line:
								print(line.split(',')[1])
							else:
								print(line)
					else:
						print(line)
				input("Press Enter to continue...")
		else:
			print("Error: file '" + args.filename + "' not found.")
		main_overlay.clear_all()
		main_overlay.refresh()
		print("Exit")
	else:
		from pywinauto_recorder.recorder import *
		from pywinauto_recorder import __version__
		from win32api import GetSystemMetrics
		recorder = Recorder()
		path_icons = Path(__file__).parent.absolute() / Path("Icons")
		icon_pywinauto_recorder = str(path_icons / Path("IconPyRec.ico"))
		icon_record = str(path_icons / Path("record.ico"))
		icon_stop = str(path_icons / Path("stop.ico"))
		icon_folder = str(path_icons / Path("folder.ico"))
		icon_search = str(path_icons / Path("search.ico"))
		icon_light_on = str(path_icons / Path("light-on.ico"))
		icon_settings = str(path_icons / Path("settings.ico"))
		icon_check = str(path_icons / Path("check.ico"))
		icon_cross = str(path_icons / Path("cross.ico"))
		icon_power = str(path_icons / Path("power.ico"))
		icon_help = str(path_icons / Path("help.ico"))
		icon_comments = str(path_icons / Path("comments.ico"))
		icon_favourite = str(path_icons / Path("favourite.ico"))
		hover_text = "Pywinauto recorder"
		
		def action_record(sysTrayIcon):
			if recorder.mode == 'Record':
				sysTrayIcon.menu_options[0][0] = "Start recording"
				sysTrayIcon.menu_options[0][1] = icon_stop
				recorder.stop_recording()
			else:
				sysTrayIcon.menu_options[0][0] = "Stop recording"
				sysTrayIcon.menu_options[0][1] = icon_record
				recorder.start_recording()

		def action_colour(sysTrayIcon):
			if recorder.mode == 'Stop':
				sysTrayIcon.menu_options[1][0] = "Stop colouring"
				sysTrayIcon.menu_options[1][1] = icon_pywinauto_recorder
				recorder.mode = 'Pause'
			else:
				sysTrayIcon.menu_options[1][0] = "Start colouring"
				sysTrayIcon.menu_options[1][1] = icon_stop
				recorder.mode = 'Stop'

		def action_display_element_info(sysTrayIcon):
			if recorder.display_info_tip_mode:
				sysTrayIcon.menu_options[2][0] = "Start displaying element info"
				sysTrayIcon.menu_options[2][1] = icon_stop
				recorder.display_info_tip_mode = False
			else:
				sysTrayIcon.menu_options[2][0] = "Stop displaying element info"
				sysTrayIcon.menu_options[2][1] = icon_search
				recorder.display_info_tip_mode = True
				
		def action_smart_mode(sysTrayIcon):
			if recorder.smart_mode:
				sysTrayIcon.menu_options[3][0] = "Start Smart mode"
				sysTrayIcon.menu_options[3][1] = icon_stop
				recorder.smart_mode = False
			else:
				sysTrayIcon.menu_options[3][0] = "Stop Smart mode"
				sysTrayIcon.menu_options[3][1] = icon_light_on
				recorder.smart_mode = True

		def action_relative_coordinates(sysTrayIcon):
			if recorder.relative_coordinate_mode:
				sysTrayIcon.menu_options[6][2][0][1] = icon_cross
				recorder.relative_coordinate_mode = False
			else:
				sysTrayIcon.menu_options[6][2][0][1] = icon_check
				recorder.relative_coordinate_mode = True
				
		def action_process_menu_click(sysTrayIcon):
			if recorder.process_menu_click_mode:
				sysTrayIcon.menu_options[6][2][1][1] = icon_cross
				recorder.process_menu_click_mode = False
			else:
				sysTrayIcon.menu_options[6][2][1][1] = icon_check
				recorder.process_menu_click_mode = True

		def action_open_explorer(sysTrayIcon):
			pywinauto_recorder_path = Path.home() / Path("Pywinauto recorder")
			os.system('explorer "' + str(pywinauto_recorder_path) + '"')

		def action_display_help(sysTrayIcon):
			display_splash_screen()

		def action_display_web_site(sysTrayIcon):
			os.system('rundll32 url.dll,FileProtocolHandler "https://pywinauto-recorder.readthedocs.io"')
			
		def hello(sysTrayIcon):
			print("Menu 2")

		def simon(sysTrayIcon):
			print("Hello Simon.")

		menu_options = [['Start recording', icon_stop, action_record],
		                ['Stop colouring', icon_pywinauto_recorder, action_colour],
		                ['Start displaying element info', icon_stop, action_display_element_info],
		                ['Start Smart mode', icon_stop, action_smart_mode],
		                ['- - - - - -', None, hello],
		                ['Open output folder', icon_folder, action_open_explorer],
		                ['Process events', icon_settings, [
			                ['% relative coordinates', icon_cross, action_relative_coordinates],
			                ['menu_click', icon_check, action_process_menu_click],
			                ['set_text', icon_cross, hello],
			                ['set_combobox', icon_cross, hello], ]],
		                ['- - - - - -', None, hello],
		                ['Help', icon_help, [
			                ['About', icon_comments, action_display_help],
			                ['Web site', icon_favourite, action_display_web_site], ]]
		                ]
		
		def bye(sysTrayIcon):
			print("bye---->")
			recorder.quit()
			while recorder.is_alive():
				time.sleep(0.5)
			print("Exit")
			print("<----bye")

		SysTrayIcon(icon_pywinauto_recorder, hover_text, menu_options, on_quit=bye, default_menu_index=1)
		
		while recorder.is_alive():
			time.sleep(0.5)
		print("Exit2")

	sys_exit(0)

