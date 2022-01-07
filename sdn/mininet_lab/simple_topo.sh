#!/bin/bash
mn --switch ovs --controller ref --topo tree,depth=2,fanout=4 --test pingall
