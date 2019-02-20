#! /usr/bin/env python
# chatting server
# A multi-user chatting program
# @author : Yichen Jia (yjia@csc.lsu.edu)
# @Instructor : Dr.Seung-Jong Park

import sys
import socket
import select
import time
import threading
import logging

HOST = ''
PORT = 9009
RECV_BUFFER = 4096
TIMEOUT = 3

class WhatsUp(threading.Thread):
      # initialization
      def __init__(self,conn,addr):
          threading.Thread.__init__(self)
          self.conn = conn
          self.addr = addr
          self.ip = self.addr[0]
          self.name = ''
      # used for notification
      def notification(self, msg):
          self.conn.send('%s\n >>' %(msg))
      # choose an user name and passwd in the login function
      def login(self):
          global SOCKET_LIST
          global accouts
          global onlines
          global database
          
          #SOCKET_LIST.append((self.conn, self.addr))
          msg = '\n## Welcome to my chatting program. \n##Enter !q to quit\n'

          #print onlines
          if self.addr not in accounts: #If the user doesn't exist in the accounts
              msg += '## Please enter your name:'
              self.notification(msg)
              accounts[self.addr] = {
                 'name': '',
                 'pass': ''
              }
              while 1:
                 name = self.conn.recv(RECV_BUFFER).strip()
                 if name in database:
                    self.notification('## This name already exists, please try another \n')
                 else:
                    break
              accounts[self.addr]['name'] = name
              self.name = name
              logging.info('%s has been choosen as your user name. \n' % (self.name,))
              database[name]=[]
              self.notification('Hi %s,please enter your password: \n' %(self.name,))
              password = self.conn.recv(RECV_BUFFER)
              accounts[self.addr]['pass'] = password.strip()
              self.notification('##Enjoy your chatting! \n')
              SOCKET_LIST.append((self.conn, self.addr))
          else:   # if the user exists in the accounts
              self.name = accounts[self.addr]['name']
              msg += '## Hi %s, please enter your password: \n' %(self.name,)
              self.notification(msg)
              while 1:
                  password = self.conn.recv(RECV_BUFFER).strip()
                  if password != accounts[self.addr]['pass']:
                     self.notification('Incorrect password, please try again! \n')
                  else:
                     self.notification('Welcome back! \n')
                     break
              SOCKET_LIST.append((self.conn, self.addr))  
          self.broadcast(' %s is online now \n' % (self.name,),SOCKET_LIST,False)
          onlines[self.name] = (self.conn,self.addr)

       # logoff from the server 
      def logoff(self):
         global SOCKET_LIST
         global onlines
         self.conn.send('## Bye!\n')
         del onlines[self.name]
         SOCKET_LIST.remove((self.conn,self.addr))
         if onlines:
             self.broadcast('%s is offline now \n' %(self.name,),SOCKET_LIST)
         self.conn.close()
         exit()
       # block the user and put it in the list
      def block(self, usrname):
          global blocklist
          blocklist.setdefault(self.name,set())
          blocklist.setdefault(usrname,set())
          blocklist[self.name].add(onlines[usrname])
          blocklist[usrname].add(onlines[self.name])
          self.notification('## %s has been blocked\n' %(usrname,))
       #unblock the user and remove it from the blocklist   
      def unblock(self, usrname):
          global blocklist
          try :
              blocklist[self.name].remove(onlines[usrname])
              self.notification('## %s has been removed from blocklist\n' %(usrname,))
          except Exception, e:
              pass
      # create or join a group
      def group_join(self,group_name):
          global groups
          groups.setdefault(group_name,set())
          groups[group_name].add((self.conn,self.addr))
          self.notification('## You have joined the group `%s`\n' % (group_name,))
       # invite someone to join a group
      def group_invite(self, group_name, usr_name):
          global groups
          global blocklist
          groups.setdefault(group_name,set()) 
          if onlines[usr_name] not in blocklist[self.name]:
             onlines[usr_name][0].send('## Would you like to join the group `%s`,if so, please reply #%s:yes: \n' % (group_name,group_name))
      
       # When you receive a invitation to join a group, if you want to join, it goes to this function
      def group_reply(self, group_name):
          groups[group_name].add((self.conn,self.addr))
          self.conn.send('## You have joined the group `%s` successfully! \n' %(group_name,))
             
       # If you want to leave the group, it geos into this function    
      def group_leave(self, group_name):
        global groups
        try:
            groups[group_name].remove((self.conn, self.addr))
            self.notification('## You have left the group `%s` \n' % (group_name,))
        except Exception, e:
            pass
        # this function is to remove the user from the group.
      def group_remove(self, group_name, usr_name):
        global groups
        try:
           groups[group_name].remove(onlines[usr_name])
           self.notification('## `%s` has been removed out of group %s \n' %
                                 (usr_name,group_name))
        except Exception, e:
            pass
       # when you want to talk in the group, it will be limited within the group.
      def group_post(self, group_name, msg):
        global groups
        # if the group does not exist, create it
        groups.setdefault(group_name, set())

        # if current user is a member of the group
        if (self.conn, self.addr) in groups[group_name]:
            self.broadcast(msg, list(set(groups[group_name])-set(blocklist[self.name])))
        else:
            self.notification(
                '## You are current not a member of group `%s` \n' % (group_name,))    
      # To disband the group and remove all the users.
      def group_disband(self,group_name):
          global groups
          try: 
             groups.pop(group_name,None)
             self.notification('## You have disband the group `%s` \n' %
                                 (group_name,))
          except Exception, e:
             pass

      # when you want to talk with one specific client, you should use mention
      def mention(self, from_user, to_user, msg, read=0):
        global messages
        # print 'Messages', messages
        if to_user in messages:
            messages[to_user].append([from_user, msg, read])
            self.notification('## Message has sent to %s \n' % (to_user,))
        else:
            self.notification('## No such user named `%s` \n' % (to_user,))
      # check special characters and to see whether the user wants some service. 
      def check_special(self,buf):
          global onlines
          global blocklist
          if buf.find('!q') == 0: #quit
             self.logoff()
          if buf.find('$ONLINE') == 0: # View online users
             for others in onlines:
                   if self.name != others and onlines[others] not in blocklist[self.name]:
                        onlines[self.name][0].send('%s\n' %others)
             return True
          if buf.find('@') == 0: # mention
            to_user = buf.split(' ')[0][1:]
            from_user = self.name
            msg = buf.split(' ', 1)[1]

            # if user is online
            if to_user in onlines:
                if onlines[to_user] not in blocklist[self.name]:
                   onlines[to_user][0].send('%s: %s \n' % (from_user, msg) +'>>')
                   self.mention(from_user, to_user, msg, 1)
            else:
                self.notification('## No such user named `%s` \n' % (to_user,))
            return True
          if buf.find('#') == 0: # group chatting
            group_keyword = buf.split(' ')[0][1:]
            group_component = group_keyword.split(':')

            # to post in a group
            if len(group_component) == 1:
                group_name = group_component[0]
                try:
                    msg = '[%s]%s: %s' % (
                        group_name, self.name, buf.split(' ', 1)[1])
                    self.group_post(group_name, msg)
                except IndexError:
                    self.print_indicator(
                        '## What do you want to do with `#%s`? \n' % (group_name))

            # to join / leave a group
            elif len(group_component) == 2:
                group_name = group_component[0]
                if group_component[1] == 'join':
                    self.group_join(group_name)
                elif group_component[1] == 'leave':
                    self.group_leave(group_name)
                elif group_component[1] == 'disband':
                    self.group_disband(group_name)
                elif group_component[1] == 'yes':
                    self.group_reply(group_name)
            # to invite / remove users
            elif len(group_component) == 3:
                group_name = group_component[0]
                usr_name = group_component[2]
                if group_component[1] == 'invite':
                    self.group_invite(group_name, usr_name)
                if group_component[1] == 'remove':
                    self.group_remove(group_name, usr_name)
            return True 
          if buf.find('%') == 0: #block someone
            block_keyword = buf.split(' ')[0][1:]
            block_component = block_keyword.split(':')
            usrname = block_component[0]
            if block_component[1] == 'BLOCK':
               self.block(usrname)
            elif block_component[1] == 'UNBLOCK':
               self.unblock(usrname)
            return True
      #to broadcast the msg to the receivers
      def broadcast(self, msg, receivers, to_self= True):
          for socket in receivers:
            if socket[1] != self.addr: #The best place to add block list
              #print 'broadcast function'
               socket[0].send(msg + '\n >> ')
            else:
               self.conn.send('>> ')
            #if to_self: 
            #else: 
               #self.conn.send('')      
      
      def run(self):
          global messages
          global accounts
          global SOCKET_LIST
          global blocklist 
          self.login()
          blocklist.setdefault(self.name,set())
          while 1: 
              try:
                 self.conn.settimeout(TIMEOUT)
                 buf = self.conn.recv(RECV_BUFFER).strip()
                 if not self.check_special(buf):
                    #print len(blocklist[self.name])
                    #self.broadcast('%s: %s' %(self.name,buf), SOCKET_LIST)
                    self.broadcast('%s: %s' %(self.name,buf), list(set(SOCKET_LIST)-set(blocklist[self.name])))
              except Exception, e:
                 # timed out
                 pass
      
def main():
          global SOCKET_LIST
          global database
          global accounts
          global onlines
          global groups
          global blocklist

          #init the lists
          SOCKET_LIST = []
          database = {}
          accounts = {}
          onlines = {}
          groups = {}
          blocklist = {}

          #set up socket 
          server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
          server_socket.bind((HOST, PORT))
          server_socket.listen(10)

          # add server socket object to the list of readable connections
          while 1:
                      try:
                         sockfd, addr = server_socket.accept()
                         server = WhatsUp(sockfd,addr)
                         server.start()
                      except Exception, e:
                         print e    

if __name__ == "__main__":
    
    sys.exit(main())       
     
