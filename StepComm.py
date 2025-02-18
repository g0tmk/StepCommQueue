#!/python
#StepComm, a serial terminal emulator in Python
#
#Modified Oct 16, 2022 by g0tmk to add input/output queues
#
#Copyright (C) 2018  William B Hunter
#
#This program is free software: you can fgistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.


#construction Notes:
#This tkinter GUI implements a serial comms program. This consists of these parts:
# 1. serial port input and output
# 2. Keyboard input
# 3. display of RX and TX data in a text window
# 4. a series of menus (pop up windows and a menu bar) for changing settings
# 5. status bar at the bottom of the screen and debug messages on the console
#
# The serial program captures keystrokes on the text area and sends them out the
# serial port. It also copies to the text area if local echo is on. Characters
# received over the serial port are copied to the text area.
# In addition, the cap/send screen can send text strings, multiline macros, as well
# as send entire text files or capture the data to a file.
#
#There are two special self calling routines. One is used for transmitting strings,
# and one is used to capture the data received on the comport. These routines will
# call themselves after a fixed delay, causing an endless series of paced executions
# of the routines. The capture data routine is necessary because there is no tkinter
# event for a received character on a comport, so the comport must be polled.
# This is the only way to handle this in a tkinter project since any call to sleep
# effectively kills the GUI.
# The second routine is used in the transmission of strings to the serial port. A handy
# feature of a good comm program is to have an adjustable pacing of the data going
# out the comport. This take the form of a character delay and a line delay. To create
# the delays (again, without using sleep()) the txstring routine sets up the data,
# and the txchar loop outputs a single char and calls itself until the string is 
# finished. During the transmission of the string, no other string or char can be sent.
import os.path
import time
import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as tkst
from tkinter import filedialog,TOP,BOTTOM,LEFT,RIGHT
from tkinter import X,Y,N,S,E,W,END,BOTH,VERTICAL,HORIZONTAL,DISABLED
from tkinter import font
import serial
from serial.tools.list_ports import comports
import re
import sys
import json
import argparse
import queue


class pycom_tk(tk.Frame):
    
    def __init__(self,parent=None,data_from_device_q=None):
        #tk.Frame.__init__(self,parent)
        tk.Frame.__init__(self,parent)
        self.root = parent
        self.root.wm_title("StepComm - Serial Terminal Emulator in Python (C)2018 William B Hunter")
        self.grid_rowconfigure(0, weight=1) # resizable main frame
        self.grid_columnconfigure(0, weight=1) # resizable main frame
        self.data_from_device_q = data_from_device_q # queue; bytes from device are writtem there


        #####################################
        ##          HELP and TEXT          ##
        #####################################
        self.about_txt = """StepComm Rev 20181201
<c>2018 William B Hunter
A Serial Terminal Emulator with some nice features geared
towards engineers, technicians, and hobbyists who need to debug
serial controlled equipment and projects. No Warranty. Have Fun!

This program comes with ABSOLUTELY NO WARRANTY;
This is free software, and you are welcome to redistribute it
under the terms of the GNU General Public License as published by
the Free Software Foundation.

"""
        self.license_txt = """StepComm Rel 20181128
<c>2018 William B Hunter
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

This software may also be available under alternate licenses from the
copyright holder.
"""
        self.help_txt = """StepComm Rel 20181128
Help
Use the file menu to save and load configurations
Use the settings menu to select bring up additional options
  at the bottom of the window. Settings include port, cap/send, and options.
Port options allow you to control serial port settings.
cap/send options let you capture data, or send common commands or files.
options menu allows you to change the way things are displayed."""
        #####################################
        ##         global variables        ##
        #####################################
        self.bgcolor = 'white'
        self.txcolor = 'red'
        self.rxcolor = 'blue'
        self.bordcolor = "light gray"
        default_font = tk.font.nametofont("TkDefaultFont")
        default_font.configure(family="Fixedsys",size=8)
        self.screenFont = font.Font(family="Fixedsys", size=8)
        self.controlFont = font.Font(family="Fixedsys", size=8)

        self.status_text = tk.StringVar()
        self.rows = 40
        self.cols = 80

        self.parity_strings = ('NONE','EVEN','ODD','MARK','SPACE')
        self.bauds=('300','600','1200','2400','4800','9600','14400','19200',
            '28800','38400','57600','115200','230400','46800')
        self.parity_consts= (serial.PARITY_NONE,serial.PARITY_EVEN,serial.PARITY_ODD,
                        serial.PARITY_MARK,serial.PARITY_SPACE)
        self.databit_strings=('5','6','7','8')
        self.databit_consts=(serial.FIVEBITS,serial.SIXBITS,serial.SEVENBITS,serial.EIGHTBITS)
        self.stopbit_strings=('1','1.5','2')
        self.stopbit_consts=(serial.STOPBITS_ONE,serial.STOPBITS_ONE_POINT_FIVE,serial.STOPBITS_TWO)
        self.echo = tk.StringVar()
        self.comport = serial.Serial()
        #self.newline_file = '\r\n'
        #self.newline_tx = '\r\n'
        #self.newline_rx = '\r\n'
        self.nl_styles = ('WINDOWS','UNIX   ','OLD MAC','AUTO   ')
        self.nl_desc = (r'NL=\r\n',r'NL=\n',r'NL=\r','Mimic RX')
        #self.rxnl=tk.StringVar()
        #self.rxnl.set(self.nl_styles[0])
        self.txnl=tk.StringVar()
        self.txnl.set(self.nl_styles[0])
        self.fnnl=tk.StringVar()
        self.fnnl.set(self.nl_styles[1])
        #self.txnlcr = tk.IntVar()
        #self.txnlcr.set(1)
        #self.txnllf = tk.IntVar()
        #self.txnllf.set(1)
        self.txnl_autostyle = "WINDOWS"
        #self.txnl_lastchar.set('NO')
        self.txnl_ignore = ' '
        self.rxnl_ignore = ' '
        self.send_cnt = 4
        self.send_text = [tk.StringVar() for i in range(self.send_cnt)]
        self.send_hist = [[""] for i in range(self.send_cnt)]
        self.send_snl = [tk.IntVar() for i in range(self.send_cnt)]
        self.macro_text = ["" for i in range(self.send_cnt)]
        self.macro_sel = tk.IntVar()
        self.macro_sel.set(1)
        self.macro_oldsel = self.macro_sel.get()
        self.txfilename = tk.StringVar()
        self.rxfilename = tk.StringVar()
        #self.cap_file = [tk.StringVar() for i in range(self.send_cnt)]
        self.char_delay = tk.IntVar()
        self.line_delay = tk.IntVar()
        self.txbuf = ''
        self.txptr = 0
        

        self.test_text = tk.StringVar()
        self.test_hist = [""]
        self.test_snl = tk.IntVar()

        #####################################
        ##            MENU SYSTEM          ##
        #####################################
        #set up the menu bar
        self.menubar = tk.Menu(self)
        #self.majorgrid = tk.IntVar()
        #self.minorgrid = tk.IntVar()
        #self.tranaxis = tk.IntVar()
        #self.thicklines = tk.IntVar()
        #self.majorgrid.set(1)
        #self.minorgrid.set(0)
        menu = tk.Menu(self.menubar, tearoff=0)
        #file menu
        self.menubar.add_cascade(label="File", menu=menu)
        menu.add_command(label="Save Settings", command=lambda: self.filesave())
        menu.add_command(label="Load Settings", command=lambda: self.fileload())
        menu.add_separator()
        menu.add_command(label="Exit", command=lambda: self.exitapp())
        #popup controls menu
        menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Settings", menu=menu)
        menu.add_radiobutton(label="Hide Settings",command=self.hide_tabs)
        menu.add_radiobutton(label="Port Settings",command=self.show_porttab)
        menu.add_radiobutton(label="Cap/Send Settings",command=self.show_sendtab)
        menu.add_radiobutton(label="Options",command=self.show_opttab)

        #help menu
        menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=menu)
        menu.add_command(label="Quick Help", command=lambda: self.helphelp())
        menu.add_command(label="Help About", command=lambda: self.helpabout())
        #finish up menu bar
        self.root.config(menu=self.menubar)
        
        ################################
        ##         TEXT CANVAS        ##
        ################################
        
        self.textframe = tk.Frame(self, bg=self.bgcolor, width=60, height=20)
        self.textframe.grid(row=0,column=0,sticky=W+E+N+S)
        self.textarea = tkst.ScrolledText(self.textframe, wrap = tk.WORD, width=60,height=20)
        self.textarea.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        #self.textarea.grid_rowconfigure(0, weight = 1)
        #self.textarea.grid_columnconfigure(0, weight = 1)
        self.textarea.tag_configure('txtext',foreground=self.txcolor)
        self.textarea.tag_configure('rxtext',foreground=self.rxcolor)
        self.textarea.bind('<Key>', lambda e: self.typed_char(e))


        #self.textframe = tk.Frame(self, bg=self.bgcolor, 
        #        width=60, height=20)
        #self.scrollbar = tk.Scrollbar(self.textframe)
        #self.scrollbar.pack(side=RIGHT, fill=Y)
        #self.textarea = tk.Text(self.textframe, bg=self.bgcolor, fg=self.txcolor, 
        #        width=60, height=20,bd=2,
        #        font=self.screenFont, yscrollcommand=self.scrollbar.set)
        #self.textarea.bind('<Key>', lambda e: self.typed_char(e))
        #self.scrollbar.config(command=self.textarea.yview)
        #self.textarea.pack(side=TOP, fill=X)
        #self.textarea.tag_configure('txtext',foreground=self.txcolor)
        #self.textarea.tag_configure('rxtext',foreground=self.rxcolor)
        #self.textframe.pack(side=TOP, fill=X)
        ################################k
        ##         PORT SETTINGS      ##
        ################################
        #create a control frame for holding all the port controls
        self.port_frame = tk.Frame(self,height=10,bg=self.bordcolor,bd=5)
        self.port_frame.grid(row=1,column=0,sticky=S+E+W)
        self.comslist = [a[0] for a in comports()]
        self.port_label=tk.Label(self.port_frame,text="Port",bg=self.bordcolor,)
        self.port_label.grid(row=0,column=0,sticky=W)
        self.port_combo=ttk.Combobox(self.port_frame,width=12,
            height=4,values=self.comslist)
        #self.port_spin=tk.Spinbox(self.port_frame,bg="snow",width=12,
        #                          values=self.comslist, command=self.set_port)
        self.port_combo.bind("<<ComboboxSelected>>", self.set_portparm)
        self.port_combo.bind('<Double-Button-1>', self.scan_port)
        self.port_combo.grid(row=0,column=1,sticky=W)

        self.baud_label=tk.Label(self.port_frame,text="Baud",bg=self.bordcolor)
        self.baud_label.grid(row=0,column=2,sticky=W)
        self.baud_combo=ttk.Combobox(self.port_frame,width=7,
            height=4,values=self.bauds)
        self.baud_combo.bind("<<ComboboxSelected>>", self.set_portparm)
        #self.baud_spin=tk.Spinbox(self.port_frame,bg="snow",width=7,
        #    values=('300','600','1200','2400','4800','9600','14400','19200',
        #    '28800','38400','57600','115200'), command=self.set_portparm)
        self.baud_combo.grid(row=0,column=3,sticky=W)
        
        self.parity_label=tk.Label(self.port_frame,text="Parity",bg=self.bordcolor)
        self.parity_label.grid(row=0,column=4,sticky=W)
        self.parity_combo=ttk.Combobox(self.port_frame,width=7,
            values=self.parity_strings)
        self.parity_combo.bind("<<ComboboxSelected>>", self.set_portparm)
        self.parity_combo.grid(row=0,column=5,sticky=W)
        #self.parity_spin=tk.Spinbox(self.port_frame,bg="snow",width=5,
        #    values=self.parity_strings, command=self.set_portparm)
        #self.parity_spin.grid(row=0,column=5,sticky=W)
        
        self.databits_label=tk.Label(self.port_frame,text="Data bits",bg=self.bordcolor)
        self.databits_label.grid(row=0,column=6,sticky=W)
        self.databits_combo=ttk.Combobox(self.port_frame,width=3,
            values=self.databit_strings)
        self.databits_combo.bind("<<ComboboxSelected>>", self.set_portparm)
        self.databits_combo.grid(row=0,column=7,sticky=W)
        #self.databits_spin=tk.Spinbox(self.port_frame,bg="snow",width=5,
        #     values=self.databit_strings, command=self.set_portparm)
        #self.databits_spin.grid(row=0,column=7,sticky=W)
        
        self.stopbits_label=tk.Label(self.port_frame,text="Stop bits",bg=self.bordcolor)
        self.stopbits_label.grid(row=0,column=8,sticky=W)
        self.stopbits_combo=ttk.Combobox(self.port_frame,width=3,
            values=self.stopbit_strings)
        self.stopbits_combo.bind("<<ComboboxSelected>>", self.set_portparm)
        self.stopbits_combo.grid(row=0,column=9,sticky=W)
        #self.stopbits_spin=tk.Spinbox(self.port_frame,bg="snow",width=5,
        #                    values=self.stopbit_strings, command=self.set_portparm)
        #self.stopbits_spin.grid(row=0,column=9,sticky=W)
        self.echo_label = tk.Label(self.port_frame,text='Local Echo',bg=self.bordcolor)
        self.echo_label.grid(row=0,column=10,sticky=W)
        self.echo_cbox = tk.Checkbutton(self.port_frame,bg=self.bordcolor,
             onvalue='ON', offvalue='OFF', variable=self.echo)
        self.echo_cbox.grid(row=0,column=11,sticky=W)
        
        self.newline_frame = tk.Frame(self.port_frame,height=15,bg=self.bordcolor)
        self.newline_frame.grid(row=3,column=1,sticky=E+W,columnspan=10)
        self.newline_frame.grid_columnconfigure(3, weight = 1)

        #self.rxnl_lab = tk.Label(self.newline_frame,text="RX newlines",
        #    bg=self.bordcolor,font=self.controlFont)
        #self.rxnl_lab.grid(row=0,column=0,sticky=W)
        #self.rxnl_combo=ttk.Combobox(self.newline_frame,width=10,
        #    textvariable=self.rxnl,values=self.nl_styles)
        #self.rxnl_combo.bind("<<ComboboxSelected>>", self.update_newline)
        #self.rxnl_combo.grid(row=0,column=1,sticky=W)
        #self.rxnl_spin=tk.Spinbox(self.newline_frame,bg="snow",width=10,
        #                          textvariable=self.rxnl,values=self.nl_styles,
        #                          command=self.update_newline)
        #self.rxnl_spin.grid(row=0,column=1,sticky=W)
        #self.rxnlos_lab = tk.Label(self.newline_frame,text=self.nl_desc[0],width=10,
        #        bg=self.bordcolor,font=self.controlFont)
        #self.rxnlos_lab.grid(row=0,column=2,sticky=E+W)
        tk.Frame(self.newline_frame,width=20,bg=self.bordcolor).grid(row=0,column=3,
                sticky=E+W)        
        self.txnl_lab = tk.Label(self.newline_frame,text="TX newlines : ",
                bg=self.bordcolor,font=self.controlFont)
        self.txnl_lab.grid(row=0,column=0,sticky=E)
        self.txnl_combo=ttk.Combobox(self.newline_frame,width=10,
            textvariable=self.txnl,values=self.nl_styles)
        self.txnl_combo.bind("<<ComboboxSelected>>", self.update_newline)
        self.txnl_combo.grid(row=0,column=1,sticky=E)
        #self.txnl_spin=tk.Spinbox(self.newline_frame,bg="snow",width=10,
        #                          textvariable=self.txnl,values=self.nl_styles,
        #                          command=self.update_newline)
        #self.txnl_spin.grid(row=0,column=5,sticky=E)
        self.txnlos_lab = tk.Label(self.newline_frame,text=self.nl_desc[0],width=10,
                bg=self.bordcolor,font=self.controlFont)
        self.txnlos_lab.grid(row=0,column=2,sticky=E)

        #self.txdelay_frame = tk.Frame(self.port_frame,height=15,bg=self.bordcolor)
        #self.txdelay_frame.grid(row=4,column=1,sticky=W,columnspan=10)
        tk.Label(self.newline_frame,text="Char Delay",
                bg=self.bordcolor,font=self.controlFont).grid(row=0,column=4,sticky=W)
        self.chardly_spin=tk.Spinbox(self.newline_frame,bg="snow",width=4,
                from_=0,to=100,textvariable=self.char_delay)
        self.chardly_spin.grid(row=0,column=5,sticky=W)
        tk.Label(self.newline_frame,text="ms     Line Delay",
                bg=self.bordcolor,font=self.controlFont).grid(row=0,column=6,sticky=W)
        self.linedly_spin=tk.Spinbox(self.newline_frame,bg="snow",width=4,
                from_=0,to=1000,increment=10,textvariable=self.line_delay)
        self.linedly_spin.grid(row=0,column=7,sticky=W)
        
        
        
        
        #set all the default port values
        self.baud_combo.delete(0,"end");self.baud_combo.insert(0,'115200')
        self.parity_combo.delete(0,"end");self.parity_combo.insert(0,'NONE')
        self.databits_combo.delete(0,"end");self.databits_combo.insert(0,'8')
        self.stopbits_combo.delete(0,"end");self.stopbits_combo.insert(0,'1')
        self.echo.set('ON')

        ################################
        ##         SEND SETTINGS      ##
        ################################
        #create a control frame for holding all the port controls
        self.capsend_frame = tk.Frame(self,height=10,bg=self.bordcolor)
        self.capsend_frame.grid(row=1,column=0,sticky=S+E+W)
        self.capsend_frame.grid_columnconfigure(0, weight = 1)
        self.send_frame = tk.Frame(self.capsend_frame,height=10,bg=self.bordcolor)
        self.send_frame.grid(row=0,column=0,sticky=S+E+W)
        #self.send_frame.grid_rowconfigure(0, weight = 1)
        self.send_frame.grid_columnconfigure(0, weight = 1)
        self.send_frame.grid_columnconfigure(7,weight=1)
        self.send_combo = []
        self.send_snlcb = []
        self.send_btn = []
        for i in range(self.send_cnt):
            self.send_combo.append(ttk.Combobox(self.send_frame,width=40,
                textvariable=self.send_text[i],font=self.controlFont))
            self.send_combo[i]['values'] = self.send_hist[i]
            self.send_combo[i].grid(row=i,column=0,sticky=E+W)
            self.send_snlcb.append(tk.Checkbutton(self.send_frame,variable=self.send_snl[i],
                text="No NL",bg=self.bordcolor,font=self.controlFont))
            self.send_snlcb[i].grid(row=i,column=1,sticky=tk.W)
            self.send_btn.append(tk.Button(self.send_frame,width=4,height=1,bg="snow",
                text='Send',font=self.controlFont , command = lambda idx=i:self.send_btnsel(idx)))
            self.send_btn[i].grid(row=i,column=2,sticky=tk.W)
        tk.Frame(self.send_frame,width=30,bg=self.bordcolor).grid(row=0,column=3,
                rowspan=4,sticky=tk.N+E+S+W)        
        tk.Label(self.send_frame,text="Macro",bg=self.bordcolor,
                font=self.controlFont,width=6).grid(row=0,column=4,sticky=tk.W)
        self.macro_spin=tk.Spinbox(self.send_frame,bg="snow",width=2,from_=1,to=self.send_cnt,
                textvariable=self.macro_sel,command=self.set_macro)
        self.macro_spin.grid(row=0,column=5,sticky=tk.W)
        self.macro_spin.grid_columnconfigure(0, weight = 1)
        self.macro_btn = tk.Button(self.send_frame,width=4,height=1,bg="snow",
                text='Send',font=self.controlFont, 
                command = lambda: self.stringout(self.macroedit.get(1.0,END),1))
        self.macro_btn.grid(row=0,column=6,sticky=tk.W)
        self.macroedit = tkst.ScrolledText(self.send_frame, width=40,height=6)
        self.macroedit.grid(row=1,column=4,rowspan=3,columnspan=4,sticky=N+E+S+W)
        #self.macroedit.grid_rowconfigure(0, weight = 1)
        #self.macroedit.grid_columnconfigure(0, weight = 1)
        
        self.csfile_frame = tk.Frame(self.capsend_frame,height=10,bg=self.bordcolor)
        self.csfile_frame.grid(row=1,column=0,sticky=S+E+W)
        self.csfile_frame.grid_columnconfigure(4, weight = 1)

        tk.Label(self.csfile_frame,text="Send File",width=10,
                bg=self.bordcolor,font=self.controlFont).grid(row=0,column=0,sticky=W)
        self.txfile_entry=tk.Entry(self.csfile_frame,width=20,
            font=self.controlFont,textvariable=self.txfilename)
        self.txfile_entry.grid(row=0,column=1,sticky=tk.W)
        self.txfilename.set('')
        self.txbrowse_btn = tk.Button(self.csfile_frame,width=6,height=1,bg="snow",
                text='Browse',font=self.controlFont,
                command = self.txbrowse)
        self.txbrowse_btn.grid(row=0,column=2,padx=4)
        self.txsend_btn = tk.Button(self.csfile_frame,width=6,height=1,bg="snow",
                text='Send',font=self.controlFont,
                command = self.txsendfile)
        self.txsend_btn.grid(row=0,column=3,padx=4)
        tk.Frame(self.csfile_frame,width=20,bg=self.bordcolor).grid(row=0,column=4,
                sticky=E+W)        

        tk.Label(self.csfile_frame,text="Capture File",
                bg=self.bordcolor,font=self.controlFont).grid(row=0,column=5,sticky=W)
        self.rxfile_entry=tk.Entry(self.csfile_frame,width=20,
            font=self.controlFont,textvariable=self.rxfilename)
        self.rxfile_entry.grid(row=0,column=6,sticky=tk.W)
        self.rxfilename.set('./cap.txt')
        self.rxcap_btn = tk.Button(self.csfile_frame,width=6,height=1,bg="snow",
                text='Capture',font=self.controlFont,
                command = self.rxbrowse)
        self.rxcap_btn.grid(row=0,column=7,padx=4)
        #self.rxcap_btn = tk.Button(self.csfile_frame,width=6,height=1,bg="snow",
        #        text='Capture',font=self.controlFont,
        #        command = self.rxcapfile)
        #self.rxcap_btn.grid(row=0,column=8,padx=4)
        self.clrscr_btn = tk.Button(self.csfile_frame,width=6,height=1,bg="snow",
                text='ClrScr',font=self.controlFont,
                command = self.clrscr)
        self.clrscr_btn.grid(row=0,column=9,padx=4)
       
        #################################
        ##       Options SETTINGS      ##
        #################################
        #create a control frame for holding all the port controls
        #self.opt_frame = tk.Frame(self,height=10,width=300,bg=self.bordcolor)
        self.opt_frame = tk.Frame(self,height=20,bg=self.bordcolor)
        self.opt_frame.grid(row=1,column=0,sticky=S+E+W)
        

        #################################
        ##         Status Line         ##
        #################################
        #create a control frame for holding all the port controls
        #self.opt_frame = tk.Frame(self,height=10,width=300,bg=self.bordcolor)
        self.status_frame = tk.Frame(self,height=10,bg=self.bordcolor)
        self.status_frame.grid(row=2,column=0,sticky=S+E+W)
        self.status_lab = tk.Label(self.status_frame,textvariable=self.status_text,
                justify=LEFT,bg=self.bordcolor,font=self.screenFont)
        self.status_lab.pack(fill=X,expand=True,side=BOTTOM)
        #parse the command line arguments to see if an init file was passed
        ##########################################
        ##     Command Line Argument Parsing    ##
        ##########################################
        parser = argparse.ArgumentParser(description='StepComm - Simple Terminal Emulator in Python')
        parser.add_argument('-b','--baud', help='baud rate',choices=self.bauds)
        parser.add_argument('-p','--port', help='port name')
        parser.add_argument('-e','--echo', help='echo ON or OFF')
        parser.add_argument('-i','--ini', help='ini file name')
        args = parser.parse_args()
        if args.ini != None:
            print(f'ini file is {args.ini}')
            self.fileparse(args.ini)
        #command line options override the ini file
        if args.baud != None:
            self.baud_combo.delete(0,"end");self.baud_combo.insert(0,args.baud)
        if args.echo == 'ON' or args.echo == 'OFF':
            print('setting echo to ' +  jdict['echo'] + ' due to command line argument')
            self.echo.set(jdict['echo'])
        if args.port != None:
            self.port_combo.set(args.port)

        #################################
        ##         Finish Init         ##
        #################################
        self.hide_tabs()
        self.scan_port('<Double-Button-1>')
        if len(self.comslist) == 0:
            self.port_combo.set("")
        elif self.port_combo.get() not in self.comslist:
            self.port_combo.set(self.comslist[0])
        self.root.after(50, self.set_port)
        self.root.after(100, self.port_in)
        self.root.protocol("WM_DELETE_WINDOW", self.exitapp)
        
        #self.helpabout()
    def status(self,t):
        self.status_text.set(t)
    def update_newline(self,a):
        #t=self.nl_desc[self.nl_styles.index(self.txnl.get())]
        #print("update_newline TX is {:s}".format(t))
        self.txnlos_lab.configure(text=self.nl_desc[self.nl_styles.index(self.txnl.get())])
        #t=self.nl_desc[self.nl_styles.index(self.rxnl.get())]
        #print("update_newline RX is {:s}".format(t))
        #self.rxnlos_lab.configure(text=self.nl_desc[self.nl_styles.index(self.rxnl.get())])
    def hide_tabs(self):
        #print("Hide all tabs")
        self.opt_frame.grid_remove()
        self.capsend_frame.grid_remove()
        self.port_frame.grid_remove()
        #self.update()
        #tk.update()
    def show_porttab(self):
        self.hide_tabs()
        self.port_frame.grid()
        self.update()
        #print("show port tab")
    def show_sendtab(self):
        self.hide_tabs()
        self.capsend_frame.grid()
        self.update()
        #print("show send tab")
    def show_opttab(self):
        sys.stdout.flush()
        self.hide_tabs()
        self.opt_frame.grid()
        self.update()
        #print("show options tab")
    def txbrowse(self):
        fname = filedialog.askopenfilename(title='Select file to send',filetypes = (("text files","*.txt"),("all files","*.*")))
        if fname != '':
            self.txfilename.set(fname)
            print ('TX browse got {:s}'.format(fname))
    def txsendfile(self):
        try:
            file = open(self.txfilename.get(), 'r') 
            str = file.read()
            file.close()
            print('file is {:d} chars long'.format(len(str)))
            self.status("sending file{:s}".format(self.txfilename.get()))
            self.stringout(str,1)
            self.status("sent file {:s}".format(self.txfilename.get()))
        except:
            self.status("Failed to open file{:s}".format(self.txfilename.get()))
    def rxbrowse(self):
        fname = filedialog.asksaveasfilename(title='Select capture file',initialdir ='.',filetypes = (("text files","*.txt"),("all files","*.*")))
        if fname != '':
            self.rxfilename.set(fname)
            print ('Capture browse got {:s}'.format(fname))
        try:
            file = open(self.rxfilename.get(), 'w')
            str = self.textarea.get(1.0, END)
            file.write(str)
            file.close()
            print(f'captured file {self.rxfilename.get()}, wrote {len(str)} bytes')
            self.status(f'captured file {self.rxfilename.get()}, wrote {len(str)} bytes')
        except:
            self.status("Failed to write capture file ")
    def set_port(self):

        port = self.port_combo.get()
        bs = self.baud_combo.get()
        bv = int(bs)
        ps = self.parity_combo.get()
        pv = self.parity_consts[self.parity_strings.index(ps)]
        ds = self.databits_combo.get()
        dv = self.databit_consts[self.databit_strings.index(ds)]
        ss = self.stopbits_combo.get()
        sv = self.stopbit_consts[self.stopbit_strings.index(ss)]
        print('port settings are now {:s},{:s},{:s},{:s},{:s}'.format(
                    port,bs,ps,ds,ss))
        sys.stdout.flush()
        if self.comport.is_open:
            self.comport.close()
        try:
            self.comport = serial.Serial(port=port,baudrate=bv,bytesize=dv,
                    stopbits=sv, parity=pv, timeout=0, write_timeout=0.2)
            self.status('port {:s},{:s},{:s},{:s},{:s}'.format(port,bs,ps,ds,ss))
        except:
            self.status("Failed to open port '{:s}'".format(self.port_combo.get()))
    def scan_port(self,event):
        #get a fresh list of comports every time the port is updated
        self.comslist = [a[0] for a in comports()]
        self.port_combo.configure(values=self.comslist)
        if len(self.comslist) == 0:
            self.status("No Serial Ports Found!")
        else:
            self.status("Found ports: {}".format(', '.join(map(str, self.comslist))))
    def set_portparm(self,e):
        self.set_port()
    def clrscr(self):
       self.textarea.delete(1.0,END)
    def send_btnsel (self,i):
        t=self.send_text[i].get()
        s=self.send_snl[i].get()
        #print('send_btnsel i={:d}, t={:s}, s={:d} = '.format(i,t,s))
        sys.stdout.flush()
        try:
            #If this item is already in hist, move to the top
            idx = self.send_hist[i].index(t)
            self.send_hist[i].insert(0,self.send_hist[i].pop(idx))
        except ValueError:
            #if item is not in list, add to top and limit to 10 items
            self.send_hist[i].insert(0,t)
        if len(self.send_hist[i])>1 and self.send_hist[-1]=="":
            self.send_hist[i].pop()
        while len(self.send_hist[i]) > 10:
            self.send_hist[i].pop()
        self.send_combo[i]['values']=self.send_hist[i]
        self.stringout(t,s)
    def set_macro (self):
        self.macro_text[self.macro_oldsel-1]=self.macroedit.get(1.0,END)[:-1]
        self.macro_oldsel = self.macro_sel.get()
        self.macroedit.delete("1.0", END) 
        self.macroedit.insert("1.0",self.macro_text[self.macro_sel.get()-1])
    def port_in(self):
        if self.comport.isOpen():
            inlen = self.comport.in_waiting
            if inlen > 0:
                l = self.comport.read(inlen)
                # write bytes from device to other thread(s)
                if l is not None and len(l) > 0 and self.data_from_device_q:
                    try:
                        self.data_from_device_q.put_nowait(l)
                    except queue.Full:
                        print('data_from_device_q full: {} bytes dropped'.format(len(l)))
                # write bytes from device to the screen
                #print(f'port_in: l type={type(l)},len={len(l)}')
                for c in l:
                    #print('port_in: char = {:02x}, rxnl style is {:s}'.format(ord(c),self.rxnl.get())) 
                    #print(f'port_in: c type={type(c)},c={c:x}="{chr(c)}"')
                    if c == b'\l' :
                        #print('CHAR=LF')
                        if self.rxnl_ignore=='LF':
                            #print('{} LF, ignored LF'.format(self.rxnl.get()))
                            self.rxnl_ignore = ' '
                            self.txnl_autostyle = "WINDOWS"  #save auto txnl style
                        else:
                            #print('{} LF, used LF'.format(self.rxnl.get())
                            self.textarea.insert(tk.END, "\n",'rxtext')
                            self.rxnl_ignore = 'CR'                    
                    elif c == b'\r':
                        if self.rxnl_ignore=='CR':
                            #print('{} CR, ignored CR'.format(self.rxnl.get()))
                            self.rxnl_ignore = ' '
                            self.txnl_autostyle = "WINDOWS"  #save auto txnl style
        
                        else:
                            self.textarea.insert(tk.END, "\n",'rxtext')
                            #print('{} CR, used CR'.format(self.rxnl.get()))
                            self.rxnl_ignore = 'LF'
                    elif c == b'\b':
                        #print('RX CHAR=BS')
                        self.rxnl_ignore = ' '
                        try:
                            prevtagchar = self.textarea.index("rxtext.last-1c")
                            #print('last rxchar at {}'.format(prevtagchar))
                            #print('last char ascii is "{}"'.format(self.textarea.get(prevtagchar)))
                            #print('delete ascii char{} at index {}'.format(ord(self.textarea.get(prevtagchar)),prevtagchar))
                            self.textarea.delete(prevtagchar)
                        except tk.TclError:
                            pass
                            #print('no RX text to backspace over')
                    else:
                        #print('port_in = ASCII {:x}'.format(ord(c)))
                        char = chr(c)
                        self.textarea.insert(tk.END, char,'rxtext')
                        #record the auto detected TX NL style
                        if self.rxnl_ignore == 'CR':
                            self.txnl_autostyle = "OLD MAC"
                        elif self.rxnl_ignore == 'LF':
                            self.txnl_autostyle = "UNIX   "
                        self.rxnl_ignore = ' '
                self.textarea.see("end")
        self.root.after(10,self.port_in)
        #self.after(100,self.port_in)
    def typed_char(self,event):
        if len(event.char) == 1:
            #print ('character {}'.format(ord(event.char)))
            if ord(event.char) == 3:
                #ctrl-C copy of selected text to clipboard
                try:
                    txt = self.textarea.selection_get()
                    self.clipboard_clear()
                    self.clipboard_append(txt)
                except:
                    self.status('clipboard copy failed')
            elif ord(event.char) == 22:
                #ctrl-v paste text from clipboard
                try:
                    txt = self.clipboard_get()
                    self.stringout(txt,1)
                except:
                    self.status('clipboard paste failed')
            else:
                self.charout(event.char)
        return("break")
    def stringout(self,txt,snl):
        if self.txbuf != '':
            return
        else:
            if int(snl) == 1:
                self.txbuf = txt
            else:
                self.txbuf = txt + '\n'
            self.txptr = 0
            self.stringloop()
    def stringloop(self):
        if self.txptr < len(self.txbuf):
            c= self.txbuf[self.txptr]
            self.charout(c)
            self.txptr += 1
            if ord(c) == '\n':
                self.root.after(self.line_delay.get(),self.stringloop)
            else:
                self.root.after(self.char_delay.get(),self.stringloop)
        else:
            self.txbuf=''
            self.txptr=0
    def charout(self,c):
        #called from stringout/stringloop or typedchar, all line endings are already '\n' except for paste
        if c == '\n' or c == '\r':
            #print('CHAR=\\r or \\n')
            if self.txnl_ignore=='LF':
                #print('{} LF, ignored LF'.format(self.rxnl.get()))
                self.txnl_ignore = ' '
            else:
                #print('{} LF, used LF'.format(self.rxnl.get())
                self.echochar('\n')
                self.comnewline()
                self.txnl_ignore = 'CR'
        elif c == '\r':
            if self.txnl_ignore=='CR':
                #print('{} CR, ignored CR'.format(self.rxnl.get()))
                self.txnl_ignore = ' '
            else:
                #print('{} CR, used CR'.format(self.rxnl.get()))
                self.echochar('\n')
                self.comnewline()
                self.txnl_ignore = 'LF'
        elif ord(c) == 8:
            self.txnl_ignore = ' '
            self.echobackspace()
            self.comchar(c)
        else:
            self.txnl_ignore = ' '
            self.echochar(c)
            self.comchar(c)
        self.textarea.see("end")
    def echochar(self,c):
        if self.echo.get() == 'ON':
            self.textarea.insert(tk.END, c,'txtext')
    def echobackspace(self):
        if self.echo.get() == 'ON':
            try:
                prevtagchar = self.textarea.index("txtext.last-1c")
                #print('last txchar at {}'.format(prevtagchar))
                #print('last char ascii is "{}"'.format(self.textarea.get(prevtagchar)))
                #print('delete ascii char{} at index {}'.format(ord(self.textarea.get(prevtagchar)),prevtagchar))
                self.textarea.delete(prevtagchar)
            except tk.TclError:
                pass
    def comchar(self,c):
        if self.comport.isOpen():
            try:
                self.comport.write(c.encode('utf-8'))
            except:
                self.status('txwrite timeout')
                
    def comnewline(self):
        if self.txnl.get() == "WINDOWS" or (self.txnl.get()== "AUTO   " and self.txnl_autostyle =="WINDOWS"):
            self.comchar('\r')
            self.comchar('\n')
        elif self.txnl.get() == 'UNIX   ' or (self.txnl.get()== "AUTO   " and self.txnl_autostyle =="UNIX   "):
            self.comchar('\n')
        elif self.txnl.get() == 'OLD MAC' or (self.txnl.get()== "AUTO   " and self.txnl_autostyle =="OLD MAC"):
            self.comchar('\r')

    def helpabout(self):
        popup_about = tk.Tk()
        popup_about.wm_title("StepComm - About")
        label = tk.Text(popup_about)
        label.insert(tk.END, self.about_txt, 'lefty')
        label.pack(side="top", fill="x", pady=10)
        label.tag_config('lefty',justify=LEFT)
        B1 = tk.Button(popup_about, text="OK", command = popup_about.destroy)
        B1.pack()
        label.config(state=DISABLED)
        popup_about.mainloop()
    def helphelp(self):
        popup_help = tk.Tk()
        popup_help.wm_title("StepComm - Quick Help")
        label = tk.Text(popup_help)
        label.insert(END,self.help_txt,'lefty')
        label.pack(side="top", fill="x", pady=10)
        label.tag_config('lefty',justify=LEFT)
        label.config(state=DISABLED)
        B1 = tk.Button(popup_help, text="OK", command = popup_help.destroy)
        B1.pack()
        popup_help.mainloop()        
 
    def filesave(self):
        snls = [self.send_snl[i].get() for i in range(4)]
        jdict = {'title':'StepComm: saved settings','time':time.asctime(),
               'port':self.port_combo.get(),'baud':self.baud_combo.get(),
               'parity':self.parity_combo.get(),'databits':self.databits_combo.get(),
               'stopbits':self.stopbits_combo.get(),'echo':self.echo.get(),
               'sendhist':self.send_hist,'send_macro':self.macro_text,'send_snls':snls,
               'capfile':self.rxfilename.get(),
               'txnl':self.txnl.get(),'txnl_autostyle':self.txnl_autostyle}
        txt = json.dumps(jdict)
        file = filedialog.asksaveasfile(mode='w',title='Select file for saving',
                filetypes = (("Config Files","*.ini"),("all files","*.*")))
            #file = open(fn,'w')
        if file == None:
            return -1
        try:
            file.write(txt)
            self.status("saved settings to " + file.name)
        except:
            self.status('failed to save settings to ' + file.name)            
    def fileload(self):
        fn = filedialog.askopenfilename(title='Select file for loading',
            filetypes = (("Settings Files","*.ini"),("all files","*.*")))
        self.fileparse(fn)
    def fileparse(self,fn):
        fn=fn.strip()
        if not os.path.isfile(fn):
            self.status(f'Bad ini file name {fn}')
            return -1
        try:
            file = open(fn, 'r')
            txt = file.read()
        except:
            #print('failed to open ini file ' + fname)
            self.status('failed to open ini file ' + fn)            
            return -1
        if len(txt) == 0:
            self.status('Empty file ' + file.name)            
            #print('Empty file ' + file.name)
            return -1
        try:
            jdict = json.loads(txt)
        except:
            #print('failed to load json data from ' + file.name)
            self.status('failed to load json data from ' + file.name)            
            return -1
        if jdict['title'] != 'StepComm: saved settings':
            #print('file ' + file.name + ' is not valid Stepcomm ini file')
            self.status('file ' + file.name + ' is not valid Stepcomm ini file')
            return -1
        if 'port' in jdict:
            self.port_combo.delete(0,"end");self.port_combo.insert(0,jdict['port'])
        if 'baud' in jdict:
            self.baud_combo.delete(0,"end");self.baud_combo.insert(0,jdict['baud'])
        if 'parity' in jdict:
            self.parity_combo.delete(0,"end");self.parity_combo.insert(0,jdict['parity'])
        if 'databits' in jdict:
            self.databits_combo.delete(0,"end");self.databits_combo.insert(0,jdict['databits'])
        if 'stopbits' in jdict:
            self.stopbits_combo.delete(0,"end");self.stopbits_combo.insert(0,jdict['stopbits'])
        if 'echo' in jdict:
            #print('ini echo mode is ' + jdict['echo'])
            self.echo.set(jdict['echo'])
        #else:
            #print('ini echo mode not found')
        if 'port' in jdict:
            self.set_port()
        if 'sendhist' in jdict:
            self.send_hist=jdict['sendhist']
            for i in range(len(self.send_hist)):
                self.send_combo[i]['values'] = self.send_hist[i]
        if 'send_snls' in jdict:
            snls = jdict['send_snls']
            [self.send_snl[i].set(snls[i]) for i in range(len(snls))]
        if 'send_macro' in jdict:
            self.macro_sel.set(1)
            self.macro_oldsel = 1
            self.macro_text=jdict['send_macro']
            self.macroedit.delete("1.0", END) 
            self.macroedit.insert("1.0",self.macro_text[self.macro_sel.get()-1])
        if 'capfile' in jdict:
            self.rxfilename.set(jdict['capfile'])
        if 'txnl' in jdict:
            self.txnl.set(jdict['txnl'])
        if 'txnl_autostyle' in jdict:
            self.txnl_autostyle = jdict['txnl_autostyle']
        self.status("loaded settings from " + file.name)
    
    def exitapp(self):
        try:
            self.comport.close()
        except:
            pass
        self.root.destroy()
        
        
    def plotall(self):
        self.textarea.itemconfigure(self,width=self.cols, height=self.rows)

        
def main():

    root = tk.Tk()
    #root.wm_geometry("1000x500+100+100")
    app = pycom_tk(root)
    app.pack(fill=BOTH,expand=True,padx=5,pady=5)
    root.mainloop()
    
if __name__ == "__main__":
    main()

