import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const PipeSection = () => import('@/views/pipe_section/index.vue')
const Inspect = () => import('@/views/inspect/index.vue')
const Defect = () => import('@/views/defect/index.vue')
const Cctv = () => import('@/views/cctv/index.vue')
const Valve = () => import('@/views/valve/index.vue')
const Maintenance = () => import('@/views/maintenance/index.vue')
const Emergency = () => import('@/views/emergency/index.vue')
const Excavation = () => import('@/views/excavation/index.vue')
const Well = () => import('@/views/well/index.vue')
const Drainage = () => import('@/views/drainage/index.vue')
const GasDetect = () => import('@/views/gas_detect/index.vue')
const Leak = () => import('@/views/leak/index.vue')
const MeterRecord = () => import('@/views/meter_record/index.vue')
const Hydrant = () => import('@/views/hydrant/index.vue')
const HydrantReminders = () => import('@/views/hydrant_reminders/index.vue')
const Trench = () => import('@/views/trench/index.vue')
const RoadOccupy = () => import('@/views/road_occupy/index.vue')
const Backfill = () => import('@/views/backfill/index.vue')
const Corrosion = () => import('@/views/corrosion/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/pipe_section', name: 'pipe_section', component: PipeSection },
    { path: '/inspect', name: 'inspect', component: Inspect },
    { path: '/defect', name: 'defect', component: Defect },
    { path: '/cctv', name: 'cctv', component: Cctv },
    { path: '/valve', name: 'valve', component: Valve },
    { path: '/maintenance', name: 'maintenance', component: Maintenance },
    { path: '/emergency', name: 'emergency', component: Emergency },
    { path: '/excavation', name: 'excavation', component: Excavation },
    { path: '/well', name: 'well', component: Well },
    { path: '/drainage', name: 'drainage', component: Drainage },
    { path: '/gas_detect', name: 'gas_detect', component: GasDetect },
    { path: '/leak', name: 'leak', component: Leak },
    { path: '/meter_record', name: 'meter_record', component: MeterRecord },
    { path: '/hydrant', name: 'hydrant', component: Hydrant },
    { path: '/hydrant-reminders', name: 'hydrant_reminders', component: HydrantReminders },
    { path: '/trench', name: 'trench', component: Trench },
    { path: '/road_occupy', name: 'road_occupy', component: RoadOccupy },
    { path: '/backfill', name: 'backfill', component: Backfill },
    { path: '/corrosion', name: 'corrosion', component: Corrosion },
  ],
})

export default router
