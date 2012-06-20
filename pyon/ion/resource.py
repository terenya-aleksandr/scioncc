#!/usr/bin/env python

"""Resource specific definitions"""

__author__ = 'Michael Meisinger'
__license__ = 'Apache 2.0'

from pyon.core.registry import IonObjectRegistry, getextends, issubtype
from pyon.core.bootstrap import IonObject
from pyon.util.config import Config
from pyon.util.containers import DotDict, named_any

from interface.services.coi.iresource_registry_service import ResourceRegistryServiceProcessClient


# Object Types
ObjectTypes = DotDict()
OT = ObjectTypes

# Resource Types
ResourceTypes = DotDict()
RT = ResourceTypes

# Predicate Types
Predicates = DotDict()
PredicateType = DotDict()
PRED = PredicateType

# Association Types, don't confuse with predicate type!
AssociationTypes = ['H2H', 'R2R', 'H2R', 'R2H']
AssociationType = DotDict()
AssociationType.update(zip(AssociationTypes, AssociationTypes))
AT = AssociationType

# Life cycle states
LifeCycleStates = DotDict()
LCS = LifeCycleStates
LCS_NONE = "NONE"

# Life cycle events
LCE = DotDict()

lcs_workflow_defs = {}
lcs_workflows = {}

def get_predicate_type_list():
    Predicates.clear()
    Predicates.update(Config(["res/config/associations.yml"]).data['PredicateTypes'])
    return Predicates.keys()

def initialize_res_lcsms():
    """
    Initializes default and special resource type state machines
    @todo. Make dynamic later and maybe move out.
    """
    res_lifecycle = (Config(["res/config/resource_lifecycle.yml"])).data

    # Initialize the set of available resource lifecycle workflows
    lcs_workflow_defs.clear()
    lcsm_defs = res_lifecycle["LifecycleWorkflowDefinitions"]
    for wf in lcsm_defs:
        #print "****** FOUND RES WORKFLOW %s" % (wf)
        wfname = wf['name']
        clsname = wf.get('lcsm_class', None)
        if clsname:
            wf_cls = named_any(clsname)
            lcs_workflow_defs[wfname] = wf_cls(**wf)
        else:
            based_on = wf.get('based_on', None)
            wf_base = lcs_workflow_defs[based_on]
            lcs_workflow_defs[wfname] = wf_base._clone_with_restrictions(wf)

    lcs_workflows.clear()

    # Initialize the set of resource types with lifecycle
    for res_type, wf_name in res_lifecycle["LifecycleResourceTypes"].iteritems():
        lcs_workflows[res_type] = lcs_workflow_defs[wf_name]

def load_definitions():
    """Loads constants for resource, association and life cycle states.
    Make sure global module variable objects are updated, not replaced, because other modules had already
    imported them (BAD).
    """
    # Resource Types
    ot_list = getextends('IonObjectBase')
    ot_list.append('IonObjectBase')
    ObjectTypes.clear()
    ObjectTypes.update(zip(ot_list, ot_list))

    # Resource Types
    rt_list = getextends('Resource')
    rt_list.append('Resource')
    ResourceTypes.clear()
    ResourceTypes.update(zip(rt_list, rt_list))

    # Predicate Types
    pt_list = get_predicate_type_list()
    PredicateType.clear()
    PredicateType.update(zip(pt_list, pt_list))

    # Life cycle states
    initialize_res_lcsms()
    LifeCycleStates.clear()
    allstates = list(CommonResourceLifeCycleSM.BASE_STATES) + CommonResourceLifeCycleSM.STATE_ALIASES.keys()
    LifeCycleStates.update(zip(allstates, allstates))

    # Life cycle events
    LCE.clear()
    LCE.update(zip([e.upper() for e in CommonResourceLifeCycleSM.BASE_EVENTS], CommonResourceLifeCycleSM.BASE_EVENTS))

def get_restype_lcsm(restype):
    return lcs_workflows.get(restype, None)

def get_maturity_visibility(lcstate):
    if lcstate == 'RETIRED':
        return (None, None)
    return lcstate.split('_')

def is_resource(object):
    return issubtype(object._get_type(), "Resource")

class ResourceLifeCycleSM(object):
    """
    Base class for all resource type life cycle state workflows. Subclasses
    defined states and transitions.
    """
    BASE_STATES = []
    STATE_ALIASES = {}
    BASE_TRANSITIONS = {}

    def __init__(self, **kwargs):
        self.transitions = {}
        self.initial_state = kwargs.get('initial_state', None)
        self._kwargs = kwargs

    @classmethod
    def is_in_state(cls, current_state, query_state):
        return (current_state == query_state) or (current_state in cls.STATE_ALIASES[query_state])

    def _clone_with_restrictions(self, wfargs=None):
        wfargs = wfargs if not None else {}
        clone =  self.__class__(**wfargs)
        clone._apply_restrictions(**wfargs)
        return clone

    def _apply_restrictions(self, **kwargs):
        self.illegal_states = kwargs.get('illegal_states', None)
        if self.illegal_states:
            trans_new = self.transitions.copy()
            for (a_state, a_transition), a_newstate in self.transitions.iteritems():
                if a_state in self.illegal_states or a_newstate in self.illegal_states:
                    del trans_new[(a_state, a_transition)]
            self.transitions = trans_new

    def get_successor(self, current_state, transition_event):
        """
        For given current_state and transition_event, return the successor state if
        defined in the FSM transitions or None
        """
        return self.transitions.get((current_state, transition_event), None)

    def get_successors(self, some_state):
        """
        For a given state, return a dict of possible transition events => successor states
        """
        ret = {}
        for (a_state, a_transition), a_newstate in self.transitions.iteritems():
            if a_state == some_state:
                #keyed on transition because they are unique with respect to origin state
                ret[a_transition] = a_newstate

        return ret

    def get_predecessors(self, some_state):
        """
        For a given state, return a dict of possible predecessor states => the transition to move
        """
        ret = {}
        for (a_state, a_transition), a_newstate in self.transitions.iteritems():
            if a_newstate == some_state:
                #keyed on state because they are unique with respect to destination state
                ret[a_state] = a_transition

        return ret


class CommonResourceLifeCycleSM(ResourceLifeCycleSM):
    """
    Common resource type life cycle state workflow. Specialized
    clones may remove states and transitions.
    Supports hierarchical states.
    """

    MATURITY = ['DRAFT', 'PLANNED', 'DEVELOPED', 'INTEGRATED', 'DEPLOYED']
    VISIBILITY = ['PRIVATE', 'DISCOVERABLE', 'AVAILABLE']

    BASE_STATES = ["%s_%s" % (m, v) for m in MATURITY for v in VISIBILITY]
    BASE_STATES.append('RETIRED')

    STATE_ALIASES = {}

    for i in list(MATURITY) + VISIBILITY:
        matchstates = [s for s in BASE_STATES if i in s]
        if matchstates:
            STATE_ALIASES[i] = tuple(matchstates)

    STATE_ALIASES['REGISTERED'] = tuple(["%s_%s" % (m, v) for m in MATURITY if m != 'DRAFT' for v in VISIBILITY])

    # Names of transition events
    PLAN = "plan"
    DEVELOP = "develop"
    INTEGRATE = "integrate"
    DEPLOY = "deploy"
    RETIRE = "retire"


    ANNOUNCE = "announce"
    UNANNOUNCE = "unannounce"
    ENABLE = "enable"
    DISABLE = "disable"

    MAT_EVENTS = [PLAN, DEVELOP, INTEGRATE, DEPLOY, RETIRE]
    VIS_EVENTS = [ANNOUNCE, UNANNOUNCE, ENABLE, DISABLE]

    BASE_EVENTS = [
        PLAN, DEVELOP, INTEGRATE, DEPLOY,
        ENABLE, DISABLE, ANNOUNCE, UNANNOUNCE,
        RETIRE
    ]

    BASE_TRANSITIONS = {}

    for m in MATURITY:
        BASE_TRANSITIONS[("%s_%s" % (m, 'PRIVATE'), ANNOUNCE)] = "%s_%s" % (m, 'DISCOVERABLE')
        BASE_TRANSITIONS[("%s_%s" % (m, 'DISCOVERABLE'), UNANNOUNCE)] = "%s_%s" % (m, 'PRIVATE')

        BASE_TRANSITIONS[("%s_%s" % (m, 'DISCOVERABLE'), ENABLE)] = "%s_%s" % (m, 'AVAILABLE')
        BASE_TRANSITIONS[("%s_%s" % (m, 'AVAILABLE'), DISABLE)] = "%s_%s" % (m, 'DISCOVERABLE')

        BASE_TRANSITIONS[("%s_%s" % (m, 'PRIVATE'), ENABLE)] = "%s_%s" % (m, 'AVAILABLE')
        BASE_TRANSITIONS[("%s_%s" % (m, 'AVAILABLE'), UNANNOUNCE)] = "%s_%s" % (m, 'PRIVATE')

    for v in VISIBILITY:
        BASE_TRANSITIONS[("%s_%s" % ('DRAFT', v), PLAN)] = "%s_%s" % ('PLANNED', v)
        BASE_TRANSITIONS[("%s_%s" % ('DRAFT', v), RETIRE)] = 'RETIRED'

        BASE_TRANSITIONS[("%s_%s" % ('DRAFT', v), DEVELOP)] = "%s_%s" % ('DEVELOPED', v)
        BASE_TRANSITIONS[("%s_%s" % ('PLANNED', v), DEVELOP)] = "%s_%s" % ('DEVELOPED', v)
        BASE_TRANSITIONS[("%s_%s" % ('INTEGRATED', v), DEVELOP)] = "%s_%s" % ('DEVELOPED', v)
        BASE_TRANSITIONS[("%s_%s" % ('DEPLOYED', v), DEVELOP)] = "%s_%s" % ('DEVELOPED', v)

        BASE_TRANSITIONS[("%s_%s" % ('DRAFT', v), INTEGRATE)] = "%s_%s" % ('INTEGRATED', v)
        BASE_TRANSITIONS[("%s_%s" % ('PLANNED', v), INTEGRATE)] = "%s_%s" % ('INTEGRATED', v)
        BASE_TRANSITIONS[("%s_%s" % ('DEVELOPED', v), INTEGRATE)] = "%s_%s" % ('INTEGRATED', v)
        BASE_TRANSITIONS[("%s_%s" % ('DEPLOYED', v), INTEGRATE)] = "%s_%s" % ('INTEGRATED', v)

        BASE_TRANSITIONS[("%s_%s" % ('DRAFT', v), DEPLOY)] = "%s_%s" % ('DEPLOYED', v)
        BASE_TRANSITIONS[("%s_%s" % ('PLANNED', v), DEPLOY)] = "%s_%s" % ('DEPLOYED', v)
        BASE_TRANSITIONS[("%s_%s" % ('DEVELOPED', v), DEPLOY)] = "%s_%s" % ('DEPLOYED', v)
        BASE_TRANSITIONS[("%s_%s" % ('INTEGRATED', v), DEPLOY)] = "%s_%s" % ('DEPLOYED', v)

    BASE_TRANSITIONS[('REGISTERED', RETIRE)] = 'RETIRED'

    def __init__(self, **kwargs):
        super(CommonResourceLifeCycleSM, self).__init__(**kwargs)
        # Flatten transitions originating from hierarchical states
        for (s0,ev),s1 in self.BASE_TRANSITIONS.iteritems():
            assert s1 not in self.STATE_ALIASES, "Transition target state cannot be hierarchical"
            if s0 in self.STATE_ALIASES:
                for state in self.STATE_ALIASES[s0]:
                    self.transitions[(state,ev)] = s1
            else:
                self.transitions[(s0,ev)] = s1
        #import pprint; pprint.pprint(self.transitions)

    def _create_basic_transitions(self):
        pass

    def _add_constraints(self):
        pass



class ExtendedResourceContainer(object):

    def __init__(self,serv_prov):
        self.service_provider = serv_prov

    def create_extended_resource_container(self, extended_resource_type, resource_object):
        res_container = IonObject(extended_resource_type)
        res_container._id = resource_object._id
        res_container.resource = resource_object

        return res_container

    def is_association(self, predicate,  predicate_type, res):
        for predt in predicate[predicate_type]:
            if res == predt:
                return True
        return False

    def is_association_extension(self, predicate,  predicate_type, res):
        for predt in predicate[predicate_type]:
            if res in getextends(predt):
                return True
        return False

    #This method figures out appropriate association call based on the Predcicate definitions
    def find_associations(self, resource,association_predicate):

        objs = list()

        pred = Predicates[association_predicate]
        if not pred:
            return objs  #unknown association type so return empty list

        #Need to check through all of these in this order to account for specific vs base class inclusions
        if self.is_association(pred,'domain',resource.type_ ):
            objs,_ = self.service_provider.clients.resource_registry.find_objects(resource._id, association_predicate, None, False)
        elif self.is_association(pred,'range',resource.type_ ):
            objs,_ = self.service_provider.clients.resource_registry.find_subjects(None,association_predicate, resource._id, False )
        elif self.is_association_extension(pred,'domain',resource.type_ ):
            objs,_ = self.service_provider.clients.resource_registry.find_objects(resource._id, association_predicate, None, False)
        elif self.is_association_extension(pred,'range',resource.type_ ):
            objs,_ = self.service_provider.clients.resource_registry.find_subjects(None,association_predicate, resource._id, False )

        return objs


    #Returns the number of associations for a specific predicate
    def get_association_count(self, res_container, association_predicate):
        return len(self.find_associations(res_container.resource, association_predicate))

    #Refactor when object decorators are available
    def get_associated_resources(self, res_container, resource_field, association_predicate):

        objs = self.find_associations(res_container.resource, association_predicate)

        if objs:
            if res_container._schema[resource_field]['type'] == 'list':
                setattr(res_container, resource_field, objs)
            else:
                setattr(res_container, resource_field, objs[0])

        return res_container

    #Refactor when object decorators are available
    def get_owners(self, res_container, resource_field):
        owners = list()

        actors = self.find_associations(res_container.resource, PRED.hasOwner)
        for actor in actors:
            info = self.find_associations(actor, PRED.hasInfo)
            if info:
                owners.append(info[0])

        return owners


    #This method iterates over the dict of extended field names and associations
    #Called from within create once decorators are refactored in.
    def get_extended_associations(self, res_container, ext_associations):
        if ext_associations is not None:
            for ext_field in ext_associations:
                objs = self.find_associations(res_container.resource, ext_associations[ext_field])
                if objs:
                    res_container.ext_associations[ext_field] = objs
                else:
                    res_container.ext_associations[ext_field] = list()







