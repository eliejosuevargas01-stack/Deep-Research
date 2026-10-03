import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

export function createProductionRouteTree(
  components: {
    Root?: any
    Home?: any
    Research?: any
    Settings?: any
  } = {},
) {
  const rootRoute = createRootRoute(components.Root ? { component: components.Root } : {})
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    ...(components.Home ? { component: components.Home } : {}),
  })
  const researchRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/research/$id',
    ...(components.Research ? { component: components.Research } : {}),
  })
  const settingsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/settings',
    ...(components.Settings ? { component: components.Settings } : {}),
  })
  const routeTree = rootRoute.addChildren([indexRoute, researchRoute, settingsRoute])
  const router = createRouter({ routeTree })
  return { rootRoute, indexRoute, researchRoute, settingsRoute, routeTree, router }
}

export const { rootRoute, indexRoute, researchRoute, settingsRoute, routeTree, router } =
  createProductionRouteTree()
